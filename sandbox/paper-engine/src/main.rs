//! Paper execution engine (P5): simulates fills against feed quotes for a
//! strategy at lifecycle "paper", journaling state after every session.
//!
//! Usage:
//!   paper-engine --manifest <path> --ruleset <path> [--feed sim|alpaca]
//!                [--sessions N] [--out DIR]

use paper_engine::{alpaca, feed, session};

use std::path::{Path, PathBuf};

use engine_core::contracts::StrategyManifest;
use engine_core::engine::Ruleset;

use crate::feed::{AnyFeed, SimFeed};
use crate::session::{Outcome, SessionConfig};

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
    let manifest_path = arg(&args, "--manifest").ok_or("--manifest <path> required")?;
    let ruleset_path = arg(&args, "--ruleset").ok_or("--ruleset <path> required")?;
    let feed_kind = arg(&args, "--feed").unwrap_or_else(|| "sim".into());
    let sessions: usize = arg(&args, "--sessions")
        .unwrap_or_else(|| "40".into())
        .parse()
        .map_err(|e| format!("--sessions: {e}"))?;

    let manifest: StrategyManifest =
        serde_json::from_str(&std::fs::read_to_string(&manifest_path).map_err(|e| e.to_string())?)
            .map_err(|e| format!("manifest: {e}"))?;
    if manifest.lifecycle != engine_core::contracts::Lifecycle::Paper {
        return Err(format!(
            "manifest lifecycle is {:?}, not paper",
            manifest.lifecycle
        ));
    }
    let ruleset = Ruleset::load(Path::new(&ruleset_path))?;

    let repo_root = find_repo_root(&std::env::current_dir().map_err(|e| e.to_string())?)
        .ok_or("repo root not found above cwd")?;
    // Alpaca data credentials from the repo-root .env (real env vars still win).
    let _ = dotenvy::from_path(repo_root.join(".env"));
    let out_dir = arg(&args, "--out")
        .map(PathBuf::from)
        .unwrap_or_else(|| repo_root.join("data/results"));
    let cfg = SessionConfig {
        journal_path: out_dir.join(&manifest.id).join("paper_journal.jsonl"),
        repo_root,
        out_dir,
        slippage_bps: 3.0,
        fee_pct: 0.0005,
    };

    let mut feed = match feed_kind.as_str() {
        "sim" => AnyFeed::Sim(SimFeed::new(manifest.universe.clone(), sessions, 42)),
        "alpaca" => AnyFeed::Alpaca(Box::new(
            alpaca::AlpacaFeed::connect(manifest.universe.clone()).await?,
        )),
        other => return Err(format!("unknown feed {other:?}")),
    };

    match session::run(&cfg, &manifest, &ruleset, &mut feed).await? {
        Outcome::Completed { result_path } => {
            tracing::info!(?result_path, "session complete");
            println!("{}", result_path.display());
        }
        Outcome::Halted => {
            tracing::warn!("halted by KILL file — no result written");
        }
    }
    Ok(())
}
