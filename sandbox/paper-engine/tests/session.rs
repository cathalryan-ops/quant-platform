//! P5 acceptance: SMA-cross paper-trades a full sim session and emits a
//! valid result; a mid-session restart resumes from the journal with no
//! state loss; a KILL file halts before processing.

use std::path::{Path, PathBuf};

use engine_core::contracts::{PaperResult, StrategyManifest};
use engine_core::engine::{Bar, Journal, Ruleset};
use paper_engine::feed::{AnyFeed, SimFeed};
use paper_engine::session::{run, Outcome, SessionConfig};

const REPO_ROOT_REL: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/../..");

fn temp_root(name: &str) -> PathBuf {
    // A minimal repo root copy so tests can create KILL files freely.
    let root = std::env::temp_dir().join(format!("qp-{name}-{}", std::process::id()));
    std::fs::create_dir_all(root.join("live")).unwrap();
    std::fs::create_dir_all(root.join("contracts")).unwrap();
    for f in [
        "live/guardrails.toml",
        "contracts/promotion_thresholds.toml",
    ] {
        std::fs::copy(Path::new(REPO_ROOT_REL).join(f), root.join(f)).unwrap();
    }
    std::fs::write(root.join("CLAUDE.md"), "test root").unwrap();
    root
}

fn manifest() -> StrategyManifest {
    let raw = std::fs::read_to_string(
        Path::new(REPO_ROOT_REL).join("contracts/examples/strategy_manifest.json"),
    )
    .unwrap();
    let mut m: StrategyManifest = serde_json::from_str(&raw).unwrap();
    m.id = "sma-cross-test-v1".into();
    m.lifecycle = engine_core::contracts::Lifecycle::Paper;
    m
}

fn ruleset() -> Ruleset {
    serde_json::from_value(serde_json::json!({
        "schema_version": "1.0.0",
        "strategy_id": "sma-cross-test-v1",
        "family": "swing",
        "max_position_pct": 5.0,
        "params": {"type": "sma_cross", "fast": 3, "slow": 8},
        "data_snapshot": {
            "parquet_path": "data/x.parquet",
            "content_hash": "sha256:9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
            "source_feed": "synthetic_test",
            "period": {"start": "2020-01-01", "end": "2020-12-31"}
        }
    }))
    .unwrap()
}

fn config(root: &Path) -> SessionConfig {
    SessionConfig {
        repo_root: root.to_path_buf(),
        out_dir: root.join("data/results"),
        journal_path: root.join("data/results/sma-cross-test-v1/paper_journal.jsonl"),
        slippage_bps: 3.0,
        fee_pct: 0.0005,
    }
}

fn sim(sessions: usize) -> AnyFeed {
    AnyFeed::Sim(SimFeed::new(vec!["SPY".into(), "QQQ".into()], sessions, 42))
}

#[tokio::test]
async fn full_session_emits_valid_result() {
    let root = temp_root("full");
    let outcome = run(&config(&root), &manifest(), &ruleset(), &mut sim(40))
        .await
        .unwrap();
    let Outcome::Completed { result_path } = outcome else {
        panic!("expected completion")
    };
    let result: PaperResult =
        serde_json::from_str(&std::fs::read_to_string(&result_path).unwrap()).unwrap();
    assert_eq!(result.strategy_id, "sma-cross-test-v1");
    assert_eq!(result.data_snapshot.source_feed, "synthetic_test");
    assert!(
        result.metrics.num_trades > 0,
        "SMA cross should have traded"
    );
    assert!(!result.period.start.is_empty() && !result.period.end.is_empty());
    std::fs::remove_dir_all(root).ok();
}

#[tokio::test]
async fn restart_resumes_without_state_loss() {
    let root = temp_root("restart");
    let cfg = config(&root);

    // Uninterrupted 40-session reference run.
    let ref_root = temp_root("restart-ref");
    let ref_cfg = config(&ref_root);
    run(&ref_cfg, &manifest(), &ruleset(), &mut sim(40))
        .await
        .unwrap();
    let reference = Journal::load_last(&ref_cfg.journal_path).unwrap().unwrap();

    // Same 40 sessions with a crash after 20: first process only 20...
    run(&cfg, &manifest(), &ruleset(), &mut sim(20))
        .await
        .unwrap();
    let mid = Journal::load_last(&cfg.journal_path).unwrap().unwrap();
    assert_eq!(mid.equity_curve.len(), 20);

    // ...then "restart" with the full deterministic feed; the journal makes
    // the first 20 sessions no-ops and the final state must match exactly.
    run(&cfg, &manifest(), &ruleset(), &mut sim(40))
        .await
        .unwrap();
    let resumed = Journal::load_last(&cfg.journal_path).unwrap().unwrap();
    assert_eq!(
        resumed, reference,
        "restart diverged from uninterrupted run"
    );

    std::fs::remove_dir_all(root).ok();
    std::fs::remove_dir_all(ref_root).ok();
}

#[tokio::test]
async fn kill_file_halts_without_processing() {
    let root = temp_root("kill");
    std::fs::write(root.join("KILL"), "halt").unwrap();
    let outcome = run(&config(&root), &manifest(), &ruleset(), &mut sim(10))
        .await
        .unwrap();
    assert_eq!(outcome, Outcome::Halted);
    assert!(Journal::load_last(&config(&root).journal_path)
        .unwrap()
        .is_none());
    std::fs::remove_dir_all(root).ok();
}

#[tokio::test]
async fn guardrail_cap_and_market_are_enforced() {
    let root = temp_root("validate");
    let mut greedy = ruleset();
    greedy.max_position_pct = 50.0;
    let err = run(&config(&root), &manifest(), &greedy, &mut sim(5))
        .await
        .unwrap_err();
    assert!(err.contains("guardrail cap"), "{err}");
    std::fs::remove_dir_all(root).ok();
}

// --- Stop-loss overlay wired into the real session loop (not just correct
// in isolation — engine-core's own unit tests already cover the overlay's
// logic; these prove `process_session` actually calls it and that the
// forced-flat/re-arm state round-trips through a real journal restart). ---

/// SMA(1,2) ruleset: trivially easy to hand-craft an exact price path for
/// (long whenever the latest close exceeds the average of the last two).
fn stop_loss_test_ruleset() -> Ruleset {
    serde_json::from_value(serde_json::json!({
        "schema_version": "1.0.0",
        "strategy_id": "sma-cross-test-v1",
        "family": "swing",
        "max_position_pct": 5.0,
        "params": {"type": "sma_cross", "fast": 1, "slow": 2},
        "data_snapshot": {
            "parquet_path": "data/x.parquet",
            "content_hash": "sha256:9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
            "source_feed": "synthetic_test",
            "period": {"start": "2020-01-01", "end": "2020-12-31"}
        }
    }))
    .unwrap()
}

fn bar(sym: &str, date: &str, open: f64, high: f64, low: f64, close: f64) -> Bar {
    Bar {
        symbol: sym.into(),
        date: date.into(),
        open,
        high,
        low,
        close,
        volume: 1_000_000.0,
    }
}

/// SPY: rising into an entry, then a session whose CLOSE keeps the raw
/// signal long (102 > avg(101,102)) but whose LOW (95) breaches the
/// manifest's 2% stop from the entry price (101 * 0.98 = 98.98) — proving
/// the overlay, not the signal, forces the exit. Signal stays long the next
/// session too (103 > avg(102,103)) with no fresh 0->1, so re-entry must
/// stay suppressed. Session 5 drops the raw signal to 0 for real (90 <
/// avg(103,90)); session 6 rises again (95 > avg(90,95)) — a genuine fresh
/// entry that must re-arm the stop. QQQ is kept monotonically declining
/// throughout so its own signal never fires and stays out of the way.
fn stop_loss_script() -> AnyFeed {
    let d = |n: u32| format!("2030-01-{n:02}");
    let spy = |n, o, h, l, c| bar("SPY", &d(n), o, h, l, c);
    let qqq = |n, c: f64| bar("QQQ", &d(n), c + 0.5, c + 1.0, c - 1.0, c);
    AnyFeed::Script(
        vec![
            vec![spy(1, 100.0, 100.0, 100.0, 100.0), qqq(1, 200.0)],
            vec![spy(2, 101.0, 101.0, 101.0, 101.0), qqq(2, 199.0)], // entry, weight=1
            vec![spy(3, 100.0, 103.0, 95.0, 102.0), qqq(3, 198.0)],  // stop breached, forced flat
            vec![spy(4, 102.0, 103.0, 101.0, 103.0), qqq(4, 197.0)], // still raw-long, stays suppressed
            vec![spy(5, 103.0, 103.0, 88.0, 90.0), qqq(5, 196.0)], // raw signal drops to 0 naturally
            vec![spy(6, 90.0, 96.0, 90.0, 95.0), qqq(6, 195.0)],   // fresh entry, re-arms
        ]
        .into_iter(),
    )
}

fn stop_loss_config(root: &Path) -> SessionConfig {
    SessionConfig {
        repo_root: root.to_path_buf(),
        out_dir: root.join("data/results"),
        journal_path: root.join("data/results/sma-cross-test-v1/paper_journal.jsonl"),
        slippage_bps: 0.0,
        fee_pct: 0.0,
    }
}

#[tokio::test]
async fn stop_loss_forces_flat_mid_session_despite_raw_signal_staying_long() {
    let root = temp_root("stoploss-e2e");
    let cfg = stop_loss_config(&root);
    // A generous cooldown isolates this test's point — the fresh-raw-
    // transition re-arm property (A) — from Option C's price-reclaim re-arm
    // (B), covered separately in engine-core's unit tests. Session 4's
    // close (103) already reclaims this scenario's entry_price (101), so
    // with the default cooldown of 0 it would legitimately re-arm one
    // session early via (B).
    let mut stop_loss_manifest = manifest();
    stop_loss_manifest.risk.stop_loss_cooldown_sessions = 3;
    run(
        &cfg,
        &stop_loss_manifest,
        &stop_loss_test_ruleset(),
        &mut stop_loss_script(),
    )
    .await
    .unwrap();

    // Replay the journal session-by-session (one line per processed
    // session) to inspect SPY's position at each point, not just the final
    // state — proves the forced-flat happens exactly on session 3, not
    // "eventually" some other way.
    let lines: Vec<String> = std::fs::read_to_string(&cfg.journal_path)
        .unwrap()
        .lines()
        .map(str::to_string)
        .collect();
    assert_eq!(lines.len(), 6, "one journal line per session");

    let position_at = |line: &str| -> f64 {
        let v: serde_json::Value = serde_json::from_str(line).unwrap();
        v["positions"]["SPY"].as_f64().unwrap_or(0.0)
    };
    assert_eq!(position_at(&lines[0]), 0.0, "session 1: no history yet");
    assert!(position_at(&lines[1]) > 0.0, "session 2: entered long");
    assert_eq!(
        position_at(&lines[2]),
        0.0,
        "session 3: stop breached (low=95 vs entry*0.98=98.98) despite raw signal staying long — must be flat"
    );
    assert_eq!(
        position_at(&lines[3]),
        0.0,
        "session 4: raw signal still long (103 > avg(102,103)) but stop stays suppressed — no re-entry"
    );
    assert_eq!(
        position_at(&lines[4]),
        0.0,
        "session 5: raw signal itself drops to 0"
    );
    assert!(
        position_at(&lines[5]) > 0.0,
        "session 6: fresh 0->1 transition re-arms the stop — must re-enter"
    );

    std::fs::remove_dir_all(root).ok();
}

#[tokio::test]
async fn stop_loss_state_survives_a_real_session_loop_restart() {
    let root = temp_root("stoploss-restart");
    let cfg = stop_loss_config(&root);

    // Uninterrupted reference run.
    let ref_root = temp_root("stoploss-restart-ref");
    let ref_cfg = stop_loss_config(&ref_root);
    run(
        &ref_cfg,
        &manifest(),
        &stop_loss_test_ruleset(),
        &mut stop_loss_script(),
    )
    .await
    .unwrap();
    let reference = Journal::load_last(&ref_cfg.journal_path).unwrap().unwrap();
    assert!(
        reference.positions.get("SPY").copied().unwrap_or(0.0) > 0.0,
        "reference run should end back in a position (re-armed at session 6)"
    );

    // "Crash" immediately after the stop-out (session 3) — the critical
    // moment for restart-safety, since the journaled state must remember
    // "stopped, awaiting re-arm" or session 4 would wrongly re-enter.
    let AnyFeed::Script(sessions) = stop_loss_script() else {
        unreachable!()
    };
    let first_three: Vec<_> = sessions.take(3).collect();
    run(
        &cfg,
        &manifest(),
        &stop_loss_test_ruleset(),
        &mut AnyFeed::Script(first_three.into_iter()),
    )
    .await
    .unwrap();
    let mid = Journal::load_last(&cfg.journal_path).unwrap().unwrap();
    assert_eq!(
        mid.positions.get("SPY").copied().unwrap_or(0.0),
        0.0,
        "flat immediately after the stop, before restart"
    );

    // "Restart" with the full script; sessions 1-3 are no-ops (already
    // journaled), so this is really just sessions 4-6 continuing from the
    // reloaded stop-tracking state.
    run(
        &cfg,
        &manifest(),
        &stop_loss_test_ruleset(),
        &mut stop_loss_script(),
    )
    .await
    .unwrap();
    let resumed = Journal::load_last(&cfg.journal_path).unwrap().unwrap();
    assert_eq!(
        resumed, reference,
        "restart after a stop-out must reach the exact same state as an uninterrupted run \
         — if the 'stopped, awaiting re-arm' flag didn't survive the restart, session 4 would \
         have wrongly re-entered and the two runs would diverge"
    );

    std::fs::remove_dir_all(root).ok();
    std::fs::remove_dir_all(ref_root).ok();
}
