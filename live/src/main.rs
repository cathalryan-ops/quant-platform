//! Live engine binary. Dry-run (Alpaca paper endpoint) is the DEFAULT;
//! real mode requires QP_REAL_TRADING=1 AND --real AND environment="real"
//! in guardrails.toml. Startup refuses without an approved live promotion,
//! parseable guardrails, and no KILL file.
//!
//! Usage:
//!   live --manifest <path> --ruleset <path> [--mode sim|dry-run|real] [--real] [--sessions N]

use std::path::{Path, PathBuf};

use engine_core::contracts::StrategyManifest;
use engine_core::engine::Ruleset;
use live::broker::{AlpacaBroker, Broker};
use live::session::{self, LiveConfig, Outcome};
use live::startup::{self, Mode};
use paper_engine::feed::{AnyFeed, SimFeed};

fn find_repo_root(start: &Path) -> Option<PathBuf> {
    let mut cur = Some(start);
    while let Some(dir) = cur {
        if dir.join("contracts").is_dir() && dir.join("CLAUDE.md").is_file() {
            return Some(dir.to_path_buf());
        }
        cur = dir.parent();
    }
    None
}

fn arg(args: &[String], name: &str) -> Option<String> {
    args.iter()
        .position(|a| a == name)
        .and_then(|i| args.get(i + 1).cloned())
}

#[tokio::main]
async fn main() -> Result<(), String> {
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env().unwrap_or_else(|_| "info".into()),
        )
        .init();

    let args: Vec<String> = std::env::args().collect();
    let manifest: StrategyManifest = serde_json::from_str(
        &std::fs::read_to_string(arg(&args, "--manifest").ok_or("--manifest required")?)
            .map_err(|e| e.to_string())?,
    )
    .map_err(|e| format!("manifest: {e}"))?;
    let ruleset = Ruleset::load(Path::new(
        &arg(&args, "--ruleset").ok_or("--ruleset required")?,
    ))?;

    let mode = match arg(&args, "--mode").as_deref() {
        None | Some("dry-run") => Mode::DryRun,
        Some("sim") => Mode::Sim,
        Some("real") => Mode::Real,
        Some(other) => return Err(format!("unknown mode {other:?}")),
    };
    let real_flag = args.iter().any(|a| a == "--real");

    let repo_root = find_repo_root(&std::env::current_dir().map_err(|e| e.to_string())?)
        .ok_or("no repo root")?;
    let checks = startup::check(&repo_root, &manifest.id, mode, real_flag)?;
    tracing::info!(approval = ?checks.approval_path, ?mode, "startup checks passed");

    let out_dir = repo_root.join("data/live").join(&manifest.id);
    let cfg = LiveConfig {
        journal_path: out_dir.join("live_journal.jsonl"),
        orders_log: out_dir.join("orders_submitted.log"),
        repo_root: repo_root.clone(),
        out_dir,
    };

    let sessions: usize = arg(&args, "--sessions")
        .unwrap_or_else(|| "40".into())
        .parse()
        .map_err(|e| format!("--sessions: {e}"))?;
    let mut broker = match mode {
        Mode::Sim => Broker::Sim { slippage_bps: 3.0 },
        Mode::DryRun => Broker::Alpaca(Box::new(AlpacaBroker::new(false)?)),
        Mode::Real => Broker::Alpaca(Box::new(AlpacaBroker::new(true)?)),
    };
    let mut feed = match mode {
        Mode::Sim => AnyFeed::Sim(SimFeed::new(manifest.universe.clone(), sessions, 42)),
        _ => AnyFeed::Alpaca(Box::new(
            paper_engine::alpaca::AlpacaFeed::connect(manifest.universe.clone()).await?,
        )),
    };

    match session::run(
        &cfg,
        &manifest,
        &ruleset,
        &checks.guardrails,
        &mut broker,
        &mut feed,
    )
    .await?
    {
        Outcome::Completed => tracing::info!("live session loop completed"),
        Outcome::Halted => tracing::warn!("halted by KILL"),
        Outcome::CircuitBroken => tracing::error!("circuit breaker tripped — halted with KILL"),
    }
    Ok(())
}
