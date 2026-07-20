//! The session loop: bars in -> target weights -> simulated fills ->
//! journaled state; a contract-valid paper_result.json at the end.
//! Deterministic given a deterministic feed; restart-safe via the journal.

use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

use engine_core::contracts::{
    DatePeriod, PaperMetrics, PaperResult, SlippageAssumptions, StrategyManifest,
};
use engine_core::engine::{Bar, Journal, PortfolioState, Ruleset, Side};

const TRADING_DAYS: f64 = 252.0;
const MIN_TRADE_USD: f64 = 1.0;

pub struct SessionConfig {
    pub repo_root: PathBuf,
    pub out_dir: PathBuf,
    pub journal_path: PathBuf,
    pub slippage_bps: f64,
    pub fee_pct: f64,
}

#[derive(Debug, PartialEq)]
pub enum Outcome {
    Completed { result_path: PathBuf },
    Halted,
}

#[derive(serde::Deserialize)]
struct GuardrailsFile {
    capital: CapitalSection,
    limits: LimitsSection,
}
#[derive(serde::Deserialize)]
struct CapitalSection {
    base_capital_usd: f64,
}
#[derive(serde::Deserialize)]
struct LimitsSection {
    max_position_pct: f64,
}

#[derive(serde::Deserialize)]
struct ThresholdsFile {
    paper_to_live: PaperThresholds,
}
#[derive(serde::Deserialize)]
struct PaperThresholds {
    min_paper_days: u32,
    min_paper_sharpe: f64,
    max_paper_drawdown_pct: f64,
}

fn kill_file(repo_root: &Path) -> PathBuf {
    repo_root.join("KILL")
}

pub fn validate(manifest: &StrategyManifest, ruleset: &Ruleset, cap: f64) -> Result<(), String> {
    if manifest.market != engine_core::contracts::Market::UsEquities {
        return Err(format!("market {:?} is not enabled in v1", manifest.market));
    }
    if ruleset.max_position_pct > cap || manifest.risk.max_position_pct > cap {
        return Err(format!("max_position_pct exceeds guardrail cap {cap}"));
    }
    if ruleset.strategy_id != manifest.id {
        return Err("ruleset/manifest strategy id mismatch".into());
    }
    Ok(())
}

pub async fn run(
    cfg: &SessionConfig,
    manifest: &StrategyManifest,
    ruleset: &Ruleset,
    feed: &mut crate::feed::AnyFeed,
) -> Result<Outcome, String> {
    let guardrails: GuardrailsFile = toml::from_str(
        &std::fs::read_to_string(cfg.repo_root.join("live/guardrails.toml"))
            .map_err(|e| format!("guardrails: {e}"))?,
    )
    .map_err(|e| format!("guardrails parse: {e}"))?;
    validate(manifest, ruleset, guardrails.limits.max_position_pct)?;

    let mut state = Journal::load_last(&cfg.journal_path)
        .map_err(|e| format!("journal load: {e}"))?
        .unwrap_or_else(|| PortfolioState::new(guardrails.capital.base_capital_usd));
    if state.last_date.is_some() {
        tracing::info!(resume_after = ?state.last_date, "resuming from journal");
    }

    let window = ruleset.history_window();
    let mut halted = false;

    while let Some(bars) = feed.next_session().await? {
        if kill_file(&cfg.repo_root).exists() {
            tracing::warn!("KILL file present — halting and confirming halt");
            halted = true;
            break;
        }
        let date = bars[0].date.clone();
        // Restart safety: never reprocess a journaled session.
        if state.last_date.as_deref() >= Some(date.as_str()) {
            continue;
        }
        process_session(&mut state, ruleset, manifest, &bars, cfg, window, &date)?;
        Journal::append(&cfg.journal_path, &state).map_err(|e| format!("journal: {e}"))?;
        tracing::info!(%date, equity = state.equity_curve.last(), "session processed");
    }

    if halted {
        return Ok(Outcome::Halted);
    }
    let result_path = write_result(cfg, manifest, ruleset, &state)?;
    Ok(Outcome::Completed { result_path })
}

fn process_session(
    state: &mut PortfolioState,
    ruleset: &Ruleset,
    manifest: &StrategyManifest,
    bars: &[Bar],
    cfg: &SessionConfig,
    window: usize,
    date: &str,
) -> Result<(), String> {
    let mut last_close = BTreeMap::new();
    for bar in bars {
        let win = state.bars.entry(bar.symbol.clone()).or_default();
        win.push_back(bar.clone());
        while win.len() > window.max(1) {
            win.pop_front();
        }
        last_close.insert(bar.symbol.clone(), bar.close);
    }

    let equity = state.equity(&last_close);
    for bar in bars {
        let raw_weight = ruleset.target_weight(&state.bars[&bar.symbol]);
        let weight = state.apply_stop_loss(
            &bar.symbol,
            raw_weight,
            bar.close,
            bar.low,
            manifest.risk.stop_loss_pct,
        )?;
        let target_value = weight * ruleset.max_position_pct / 100.0 * equity;
        let held_qty = state.positions.get(&bar.symbol).copied().unwrap_or(0.0);
        let delta_value = target_value - held_qty * bar.close;
        if delta_value.abs() < MIN_TRADE_USD {
            continue;
        }
        let side = if delta_value > 0.0 {
            Side::Buy
        } else {
            Side::Sell
        };
        let slip = cfg.slippage_bps / 10_000.0 * if delta_value > 0.0 { 1.0 } else { -1.0 };
        let price = bar.close * (1.0 + slip);
        let qty = delta_value / bar.close;
        let notional = qty.abs() * price;
        let fees = notional * cfg.fee_pct;
        state.cash -= qty * price + fees;
        let pos = state.positions.entry(bar.symbol.clone()).or_insert(0.0);
        *pos += qty;
        if pos.abs() < 1e-9 {
            state.positions.remove(&bar.symbol);
        }
        state.fills += 1;
        tracing::debug!(symbol = %bar.symbol, ?side, qty, price, "simulated fill");
    }
    state.equity_curve.push(state.equity(&last_close));
    if state.first_date.is_none() {
        state.first_date = Some(date.to_string());
    }
    state.last_date = Some(date.to_string());
    Ok(())
}

fn write_result(
    cfg: &SessionConfig,
    manifest: &StrategyManifest,
    ruleset: &Ruleset,
    state: &PortfolioState,
) -> Result<PathBuf, String> {
    let thresholds: ThresholdsFile = toml::from_str(
        &std::fs::read_to_string(cfg.repo_root.join("contracts/promotion_thresholds.toml"))
            .map_err(|e| format!("thresholds: {e}"))?,
    )
    .map_err(|e| format!("thresholds parse: {e}"))?;

    let returns: Vec<f64> = state
        .equity_curve
        .windows(2)
        .map(|w| w[1] / w[0] - 1.0)
        .collect();
    let sharpe = annualized_sharpe(&returns);
    let sortino = annualized_sortino(&returns);
    let max_dd_pct = max_drawdown_pct(&state.equity_curve);
    let start_equity = state.equity_curve.first().copied().unwrap_or(0.0);
    let end_equity = state.equity_curve.last().copied().unwrap_or(start_equity);
    let days = state.equity_curve.len() as u32;

    let out_dir = cfg.out_dir.join(&manifest.id);
    std::fs::create_dir_all(&out_dir).map_err(|e| e.to_string())?;
    let equity_csv = out_dir.join("paper_equity.csv");
    let csv: String = std::iter::once("equity\n".to_string())
        .chain(state.equity_curve.iter().map(|v| format!("{v}\n")))
        .collect();
    std::fs::write(&equity_csv, csv).map_err(|e| e.to_string())?;

    let t = &thresholds.paper_to_live;
    let result = PaperResult {
        schema_version: "1.0.0".into(),
        strategy_id: manifest.id.clone(),
        period: DatePeriod {
            start: state.first_date.clone().unwrap_or_default(),
            end: state.last_date.clone().unwrap_or_default(),
        },
        metrics: PaperMetrics {
            sharpe: round6(sharpe),
            sortino: round6(sortino),
            max_drawdown_pct: round6(max_dd_pct),
            pnl_usd: round6(end_equity - start_equity),
            num_trades: state.fills,
        },
        slippage: SlippageAssumptions {
            model: "quote_close_plus_bps".into(),
            bps: cfg.slippage_bps,
        },
        equity_curve_path: equity_csv.to_string_lossy().into_owned(),
        data_snapshot: ruleset.data_snapshot.clone(),
        passed_thresholds: days >= t.min_paper_days
            && sharpe >= t.min_paper_sharpe
            && max_dd_pct <= t.max_paper_drawdown_pct,
        notes: format!("{days} sessions simulated against feed quotes; fitted-parameter ruleset."),
        generated_at: chrono::Utc::now().format("%Y-%m-%dT%H:%M:%SZ").to_string(),
    };
    let path = out_dir.join("paper_result.json");
    std::fs::write(
        &path,
        serde_json::to_string_pretty(&result).map_err(|e| e.to_string())? + "\n",
    )
    .map_err(|e| e.to_string())?;
    Ok(path)
}

fn round6(x: f64) -> f64 {
    (x * 1e6).round() / 1e6
}

fn annualized_sharpe(returns: &[f64]) -> f64 {
    if returns.len() < 2 {
        return 0.0;
    }
    let mean = returns.iter().sum::<f64>() / returns.len() as f64;
    let var = returns.iter().map(|r| (r - mean).powi(2)).sum::<f64>() / (returns.len() - 1) as f64;
    if var == 0.0 {
        return 0.0;
    }
    mean / var.sqrt() * TRADING_DAYS.sqrt()
}

fn annualized_sortino(returns: &[f64]) -> f64 {
    if returns.len() < 2 {
        return 0.0;
    }
    let mean = returns.iter().sum::<f64>() / returns.len() as f64;
    let downside =
        (returns.iter().map(|r| r.min(0.0).powi(2)).sum::<f64>() / returns.len() as f64).sqrt();
    if downside == 0.0 {
        return 0.0;
    }
    mean / downside * TRADING_DAYS.sqrt()
}

fn max_drawdown_pct(equity: &[f64]) -> f64 {
    let mut peak = f64::MIN;
    let mut max_dd = 0.0f64;
    for &v in equity {
        peak = peak.max(v);
        if peak > 0.0 {
            max_dd = max_dd.max((peak - v) / peak);
        }
    }
    max_dd * 100.0
}
