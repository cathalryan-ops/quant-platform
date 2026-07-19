//! Startup refusals — the live engine will not start unless every safety
//! condition holds. Refusal is loud: a reason and (where useful) an event.

use std::path::{Path, PathBuf};

use engine_core::contracts::Promotion;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Mode {
    /// Offline simulated fills (tests, rehearsals).
    Sim,
    /// DEFAULT: real order path against Alpaca's PAPER endpoint. Zero risk.
    DryRun,
    /// Real money. Requires the triple gate.
    Real,
}

#[derive(Debug, serde::Deserialize)]
pub struct Guardrails {
    pub capital: Capital,
    pub limits: Limits,
}
#[derive(Debug, serde::Deserialize)]
pub struct Capital {
    pub base_capital_usd: f64,
    pub environment: String,
}
#[derive(Debug, serde::Deserialize)]
pub struct Limits {
    pub max_position_pct: f64,
    pub max_daily_loss_pct: f64,
    pub max_order_rate_per_min: u32,
}

pub fn load_guardrails(repo_root: &Path) -> Result<Guardrails, String> {
    let path = repo_root.join("live/guardrails.toml");
    toml::from_str(&std::fs::read_to_string(&path).map_err(|e| format!("read {path:?}: {e}"))?)
        .map_err(|e| format!("guardrails.toml invalid — refusing to start: {e}"))
}

/// The approved promotion record authorising this strategy to trade live.
/// Scans data/promotions/ for strategy_id -> live with a COMPLETE two-step
/// approval; anything less is a refusal.
pub fn find_live_approval(repo_root: &Path, strategy_id: &str) -> Result<PathBuf, String> {
    let dir = repo_root.join("data/promotions");
    let mut best: Option<PathBuf> = None;
    if dir.exists() {
        for path in dir.read_dir().map_err(|e| e.to_string())?.flatten() {
            let path = path.path();
            if path.extension().is_none_or(|e| e != "json") {
                continue;
            }
            let Ok(raw) = std::fs::read_to_string(&path) else {
                continue;
            };
            let Ok(promo) = serde_json::from_str::<Promotion>(&raw) else {
                continue;
            };
            if promo.strategy_id == strategy_id
                && promo.to_stage == engine_core::contracts::Lifecycle::Live
                && promo.human_approval.is_complete()
            {
                best = Some(path);
            }
        }
    }
    best.ok_or_else(|| {
        format!(
            "no approved live promotion for {strategy_id:?} \
             (complete two-step human_approval required) — refusing to start"
        )
    })
}

#[derive(Debug)]
pub struct StartupChecks {
    pub guardrails: Guardrails,
    pub approval_path: PathBuf,
}

/// All-or-nothing startup gate.
pub fn check(
    repo_root: &Path,
    strategy_id: &str,
    mode: Mode,
    real_flag: bool,
) -> Result<StartupChecks, String> {
    if repo_root.join("KILL").exists() {
        return Err("KILL file present — refusing to start".into());
    }
    let guardrails = load_guardrails(repo_root)?;
    let approval_path = find_live_approval(repo_root, strategy_id)?;

    if mode == Mode::Real {
        // Triple gate: env var AND CLI flag AND guardrails environment.
        if std::env::var("QP_REAL_TRADING").as_deref() != Ok("1") {
            return Err("real mode requires QP_REAL_TRADING=1 — refusing".into());
        }
        if !real_flag {
            return Err("real mode requires the --real flag — refusing".into());
        }
        if guardrails.capital.environment != "real" {
            return Err(
                "real mode requires environment = \"real\" in guardrails.toml — refusing".into(),
            );
        }
    }
    Ok(StartupChecks {
        guardrails,
        approval_path,
    })
}
