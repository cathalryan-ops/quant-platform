//! P8 acceptance: refuses to start without approvals / with KILL / without
//! the real-mode triple gate; trades in sim with idempotent order ids that
//! survive a restart; trips the circuit breaker on a crafted crash
//! (flatten + freeze + alert + KILL).

use std::path::{Path, PathBuf};

use engine_core::contracts::StrategyManifest;
use engine_core::engine::{Bar, Journal, Ruleset};
use live::broker::Broker;
use live::session::{run, LiveConfig, Outcome};
use live::startup::{check, Mode};
use paper_engine::feed::{AnyFeed, SimFeed};

const REPO_ROOT_REL: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/..");

fn temp_root(name: &str) -> PathBuf {
    let root = std::env::temp_dir().join(format!("qp-live-{name}-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&root);
    std::fs::create_dir_all(root.join("live")).unwrap();
    std::fs::create_dir_all(root.join("contracts")).unwrap();
    std::fs::copy(
        Path::new(REPO_ROOT_REL).join("live/guardrails.toml"),
        root.join("live/guardrails.toml"),
    )
    .unwrap();
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
    m.lifecycle = engine_core::contracts::Lifecycle::Live;
    m
}

fn ruleset() -> Ruleset {
    serde_json::from_value(serde_json::json!({
        "schema_version": "1.0.0",
        "strategy_id": "sma-cross-test-v1",
        "family": "swing",
        "max_position_pct": 5.0,
        "params": {"type": "sma_cross", "fast": 2, "slow": 3},
        "data_snapshot": {
            "parquet_path": "data/x.parquet",
            "content_hash": "sha256:9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
            "source_feed": "synthetic_test",
            "period": {"start": "2020-01-01", "end": "2020-12-31"}
        }
    }))
    .unwrap()
}

fn seed_approval(root: &Path, complete: bool) {
    let dir = root.join("data/promotions");
    std::fs::create_dir_all(&dir).unwrap();
    let approval = if complete {
        serde_json::json!({"required": true, "telegram_msg_id": 1024, "confirmation_msg_id": 1031, "approved_at": "2026-07-19T19:05:00Z"})
    } else {
        serde_json::json!({"required": true, "telegram_msg_id": 1024, "confirmation_msg_id": null, "approved_at": null})
    };
    let promo = serde_json::json!({
        "schema_version": "1.0.0",
        "id": "promo-2026-07-19-sma-cross-test-v1-live",
        "strategy_id": "sma-cross-test-v1",
        "from_stage": "paper",
        "to_stage": "live",
        "evidence": ["data/results/sma-cross-test-v1/paper_result.json"],
        "rationale": "test",
        "issued_at": "2026-07-19T19:00:00Z",
        "human_approval": approval,
    });
    std::fs::write(
        dir.join("promo-2026-07-19-sma-cross-test-v1-live.json"),
        promo.to_string(),
    )
    .unwrap();
}

fn config(root: &Path) -> LiveConfig {
    LiveConfig {
        repo_root: root.to_path_buf(),
        out_dir: root.join("data/live/sma-cross-test-v1"),
        journal_path: root.join("data/live/sma-cross-test-v1/live_journal.jsonl"),
        orders_log: root.join("data/live/sma-cross-test-v1/orders_submitted.log"),
    }
}

#[test]
fn startup_refuses_without_complete_approval() {
    let root = temp_root("no-approval");
    let err = check(&root, "sma-cross-test-v1", Mode::Sim, false).unwrap_err();
    assert!(err.contains("refusing to start"), "{err}");

    seed_approval(&root, false); // one-step only — still refused
    let err = check(&root, "sma-cross-test-v1", Mode::Sim, false).unwrap_err();
    assert!(err.contains("two-step"), "{err}");

    seed_approval(&root, true);
    assert!(check(&root, "sma-cross-test-v1", Mode::Sim, false).is_ok());
}

#[test]
fn startup_refuses_with_kill_or_bad_guardrails() {
    let root = temp_root("kill-guardrails");
    seed_approval(&root, true);
    std::fs::write(root.join("KILL"), "halt").unwrap();
    assert!(check(&root, "sma-cross-test-v1", Mode::Sim, false)
        .unwrap_err()
        .contains("KILL"));
    std::fs::remove_file(root.join("KILL")).unwrap();

    std::fs::write(root.join("live/guardrails.toml"), "not [valid toml").unwrap();
    assert!(check(&root, "sma-cross-test-v1", Mode::Sim, false)
        .unwrap_err()
        .contains("guardrails"));
}

#[test]
fn real_mode_requires_triple_gate() {
    let root = temp_root("triple-gate");
    seed_approval(&root, true);
    // No env var:
    std::env::remove_var("QP_REAL_TRADING");
    assert!(check(&root, "sma-cross-test-v1", Mode::Real, true)
        .unwrap_err()
        .contains("QP_REAL_TRADING"));
    // Env var but no flag:
    std::env::set_var("QP_REAL_TRADING", "1");
    assert!(check(&root, "sma-cross-test-v1", Mode::Real, false)
        .unwrap_err()
        .contains("--real"));
    // Env + flag but guardrails says paper:
    assert!(check(&root, "sma-cross-test-v1", Mode::Real, true)
        .unwrap_err()
        .contains("environment"));
    std::env::remove_var("QP_REAL_TRADING");
}

#[tokio::test]
async fn sim_run_is_idempotent_across_restart() {
    let root = temp_root("idempotent");
    seed_approval(&root, true);
    let checks = check(&root, "sma-cross-test-v1", Mode::Sim, false).unwrap();
    let cfg = config(&root);
    let mut broker = Broker::Sim { slippage_bps: 3.0 };

    let mut feed = AnyFeed::Sim(SimFeed::new(vec!["SPY".into(), "QQQ".into()], 15, 42));
    run(
        &cfg,
        &manifest(),
        &ruleset(),
        &checks.guardrails,
        &mut broker,
        &mut feed,
    )
    .await
    .unwrap();
    let after_first = Journal::load_last(&cfg.journal_path).unwrap().unwrap();
    assert!(after_first.fills > 0, "should have traded");
    let ids_first = std::fs::read_to_string(&cfg.orders_log).unwrap();

    // "Restart" over the same deterministic sessions: journaled sessions are
    // skipped and no order id is ever resubmitted.
    let mut feed = AnyFeed::Sim(SimFeed::new(vec!["SPY".into(), "QQQ".into()], 15, 42));
    run(
        &cfg,
        &manifest(),
        &ruleset(),
        &checks.guardrails,
        &mut broker,
        &mut feed,
    )
    .await
    .unwrap();
    let after_second = Journal::load_last(&cfg.journal_path).unwrap().unwrap();
    assert_eq!(after_first, after_second, "restart must not change state");
    assert_eq!(ids_first, std::fs::read_to_string(&cfg.orders_log).unwrap());
}

#[tokio::test]
async fn circuit_breaker_flattens_freezes_alerts_and_kills() {
    let root = temp_root("breaker");
    seed_approval(&root, true);
    let checks = check(&root, "sma-cross-test-v1", Mode::Sim, false).unwrap();
    let cfg = config(&root);
    let mut broker = Broker::Sim { slippage_bps: 3.0 };

    let bar = |sym: &str, date: &str, px: f64| Bar {
        symbol: sym.into(),
        date: date.into(),
        open: px,
        high: px,
        low: px,
        close: px,
        volume: 1.0,
    };
    // Rising prices to get long, then a 90% crash: position loss ~= $4.5k
    // on a $5k position >= the $2k (2%) daily-loss guardrail.
    let sessions = vec![
        vec![
            bar("SPY", "2030-01-02", 100.0),
            bar("QQQ", "2030-01-02", 200.0),
        ],
        vec![
            bar("SPY", "2030-01-03", 101.0),
            bar("QQQ", "2030-01-03", 202.0),
        ],
        vec![
            bar("SPY", "2030-01-04", 102.0),
            bar("QQQ", "2030-01-04", 204.0),
        ],
        vec![
            bar("SPY", "2030-01-05", 103.0),
            bar("QQQ", "2030-01-05", 206.0),
        ],
        vec![
            bar("SPY", "2030-01-06", 10.0),
            bar("QQQ", "2030-01-06", 20.0),
        ],
    ];
    let mut feed = AnyFeed::Script(sessions.into_iter());
    let outcome = run(
        &cfg,
        &manifest(),
        &ruleset(),
        &checks.guardrails,
        &mut broker,
        &mut feed,
    )
    .await
    .unwrap();

    assert_eq!(outcome, Outcome::CircuitBroken);
    assert!(root.join("KILL").exists(), "KILL must be dropped");
    let final_state = Journal::load_last(&cfg.journal_path).unwrap().unwrap();
    assert!(
        final_state.positions.is_empty(),
        "must be flat: {:?}",
        final_state.positions
    );
    let events: Vec<_> = std::fs::read_dir(root.join("infra/telegram/queue"))
        .unwrap()
        .flatten()
        .map(|e| std::fs::read_to_string(e.path()).unwrap())
        .collect();
    assert!(
        events
            .iter()
            .any(|e| e.contains("circuit_breaker") && e.contains("critical")),
        "critical circuit_breaker event must be queued"
    );

    // And the engine refuses to start again while KILL stands.
    assert!(check(&root, "sma-cross-test-v1", Mode::Sim, false)
        .unwrap_err()
        .contains("KILL"));
}

// --- Stop-loss overlay wired into the real live session loop. Mirrors
// sandbox/paper-engine/tests/session.rs's equivalent tests (same scripted
// scenario) — engine-core's own unit tests cover the overlay's logic in
// isolation; these prove `live::session::run` actually calls it. ---

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

fn ohlc_bar(sym: &str, date: &str, open: f64, high: f64, low: f64, close: f64) -> Bar {
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

/// Same scenario as paper-engine's equivalent test: SPY enters long at
/// session 2, session 3's low (95) breaches the 2% stop from the entry
/// price (101 * 0.98 = 98.98) despite the close (102) keeping the raw
/// signal long — the overlay, not the signal, must force flat. Session 4
/// stays raw-long with no fresh 0->1, so the stop stays suppressed. Session
/// 5 drops the raw signal to 0 for real; session 6's fresh 0->1 re-arms.
/// QQQ declines monotonically throughout so its own signal never fires.
fn stop_loss_script() -> AnyFeed {
    let d = |n: u32| format!("2030-01-{n:02}");
    let spy = |n, o, h, l, c| ohlc_bar("SPY", &d(n), o, h, l, c);
    let qqq = |n, c: f64| ohlc_bar("QQQ", &d(n), c + 0.5, c + 1.0, c - 1.0, c);
    AnyFeed::Script(
        vec![
            vec![spy(1, 100.0, 100.0, 100.0, 100.0), qqq(1, 200.0)],
            vec![spy(2, 101.0, 101.0, 101.0, 101.0), qqq(2, 199.0)],
            vec![spy(3, 100.0, 103.0, 95.0, 102.0), qqq(3, 198.0)],
            vec![spy(4, 102.0, 103.0, 101.0, 103.0), qqq(4, 197.0)],
            vec![spy(5, 103.0, 103.0, 88.0, 90.0), qqq(5, 196.0)],
            vec![spy(6, 90.0, 96.0, 90.0, 95.0), qqq(6, 195.0)],
        ]
        .into_iter(),
    )
}

#[tokio::test]
async fn stop_loss_forces_flat_mid_session_in_the_live_engine() {
    let root = temp_root("live-stoploss-e2e");
    seed_approval(&root, true);
    let checks = check(&root, "sma-cross-test-v1", Mode::Sim, false).unwrap();
    let cfg = config(&root);
    let mut broker = Broker::Sim { slippage_bps: 0.0 };

    run(
        &cfg,
        &manifest(),
        &stop_loss_test_ruleset(),
        &checks.guardrails,
        &mut broker,
        &mut stop_loss_script(),
    )
    .await
    .unwrap();

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
        "session 3: stop breached despite raw signal staying long"
    );
    assert_eq!(
        position_at(&lines[3]),
        0.0,
        "session 4: still raw-long, no fresh transition — stop stays suppressed"
    );
    assert_eq!(
        position_at(&lines[4]),
        0.0,
        "session 5: raw signal itself drops to 0"
    );
    assert!(
        position_at(&lines[5]) > 0.0,
        "session 6: fresh 0->1 transition re-arms the stop"
    );
}

#[tokio::test]
async fn stop_loss_state_survives_a_real_live_engine_restart() {
    let root = temp_root("live-stoploss-restart");
    seed_approval(&root, true);
    let checks = check(&root, "sma-cross-test-v1", Mode::Sim, false).unwrap();
    let cfg = config(&root);
    let mut broker = Broker::Sim { slippage_bps: 0.0 };

    // Uninterrupted reference run.
    let ref_root = temp_root("live-stoploss-restart-ref");
    seed_approval(&ref_root, true);
    let ref_checks = check(&ref_root, "sma-cross-test-v1", Mode::Sim, false).unwrap();
    let ref_cfg = config(&ref_root);
    let mut ref_broker = Broker::Sim { slippage_bps: 0.0 };
    run(
        &ref_cfg,
        &manifest(),
        &stop_loss_test_ruleset(),
        &ref_checks.guardrails,
        &mut ref_broker,
        &mut stop_loss_script(),
    )
    .await
    .unwrap();
    let reference = Journal::load_last(&ref_cfg.journal_path).unwrap().unwrap();
    assert!(
        reference.positions.get("SPY").copied().unwrap_or(0.0) > 0.0,
        "reference run should end back in a position (re-armed at session 6)"
    );

    // "Crash" immediately after the stop-out (session 3) — SPY is already
    // flat at this point, so live's broker-ledger reconciliation on restart
    // (which always adopts Broker::Sim's empty position report) cannot mask
    // a real divergence here; this specifically isolates the stop-tracking
    // state (in_position/stopped/entry_price), not position reconciliation.
    let AnyFeed::Script(sessions) = stop_loss_script() else {
        unreachable!()
    };
    let first_three: Vec<_> = sessions.take(3).collect();
    run(
        &cfg,
        &manifest(),
        &stop_loss_test_ruleset(),
        &checks.guardrails,
        &mut broker,
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

    // "Restart": sessions 1-3 are no-ops (already journaled); this
    // continues from the reloaded stop-tracking state through sessions 4-6.
    run(
        &cfg,
        &manifest(),
        &stop_loss_test_ruleset(),
        &checks.guardrails,
        &mut broker,
        &mut stop_loss_script(),
    )
    .await
    .unwrap();
    let resumed = Journal::load_last(&cfg.journal_path).unwrap().unwrap();
    assert_eq!(
        resumed, reference,
        "restart after a stop-out must reach the exact same state as an uninterrupted run \
         — if 'stopped, awaiting re-arm' didn't survive the restart, session 4 would have \
         wrongly re-entered and the two runs would diverge"
    );
}
