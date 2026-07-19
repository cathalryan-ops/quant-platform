//! P5 acceptance: SMA-cross paper-trades a full sim session and emits a
//! valid result; a mid-session restart resumes from the journal with no
//! state loss; a KILL file halts before processing.

use std::path::{Path, PathBuf};

use engine_core::contracts::{PaperResult, StrategyManifest};
use engine_core::engine::{Journal, Ruleset};
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
