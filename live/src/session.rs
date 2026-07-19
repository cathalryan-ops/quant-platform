//! The live session loop. Same cadence as the paper engine, but orders go
//! through the Broker and the guardrails are enforced INSIDE the order path:
//! max position size, max order rate, and the max-daily-loss circuit breaker
//! (auto-flatten -> freeze -> Telegram alert -> root KILL).

use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

use engine_core::contracts::StrategyManifest;
use engine_core::engine::{Fill, Journal, Order, PortfolioState, Ruleset, Side};
use paper_engine::feed::AnyFeed;

use crate::broker::Broker;
use crate::startup::Guardrails;

const MIN_TRADE_USD: f64 = 1.0;

pub struct LiveConfig {
    pub repo_root: PathBuf,
    pub out_dir: PathBuf,
    pub journal_path: PathBuf,
    pub orders_log: PathBuf,
}

#[derive(Debug, PartialEq)]
pub enum Outcome {
    Completed,
    Halted,
    CircuitBroken,
}

fn emit_event(repo_root: &Path, severity: &str, kind: &str, text: String, requires_reply: bool) {
    let ts = chrono::Utc::now().format("%Y-%m-%dT%H:%M:%SZ").to_string();
    let id = format!(
        "evt-live-{}-{}",
        kind.replace('_', "-"),
        chrono::Utc::now().format("%Y%m%d%H%M%S%f")
    );
    let event = serde_json::json!({
        "schema_version": "1.0.0",
        "id": id,
        "source_agent": "live-engine",
        "severity": severity,
        "kind": kind,
        "payload": {"text": text},
        "requires_reply": requires_reply,
        "ts": ts,
    });
    let qdir = repo_root.join("infra/telegram/queue");
    if std::fs::create_dir_all(&qdir).is_ok() {
        let _ = std::fs::write(qdir.join(format!("{id}.json")), event.to_string());
    }
}

/// Client order ids already submitted (crash-safe dedupe, one id per line).
fn submitted_ids(path: &Path) -> std::collections::BTreeSet<String> {
    std::fs::read_to_string(path)
        .map(|s| s.lines().map(str::to_string).collect())
        .unwrap_or_default()
}

fn record_submission(path: &Path, id: &str) -> Result<(), String> {
    use std::io::Write;
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    let mut f = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(path)
        .map_err(|e| e.to_string())?;
    writeln!(f, "{id}").map_err(|e| e.to_string())?;
    f.sync_all().map_err(|e| e.to_string())
}

/// Startup reconciliation: the broker's ledger is the truth for positions.
pub async fn reconcile(
    state: &mut PortfolioState,
    broker: &Broker,
    repo_root: &Path,
) -> Result<(), String> {
    let broker_positions = broker.positions().await?;
    if broker_positions != state.positions {
        tracing::warn!(?broker_positions, local = ?state.positions, "reconciliation divergence — adopting broker ledger");
        emit_event(
            repo_root,
            "warning",
            "reconciliation",
            format!(
                "local {:?} vs broker {:?}; adopted broker",
                state.positions, broker_positions
            ),
            false,
        );
        state.positions = broker_positions;
    }
    let cancelled = broker.cancel_open_orders().await?;
    if cancelled > 0 {
        emit_event(
            repo_root,
            "warning",
            "orphan_orders_cancelled",
            format!("{cancelled} open orders cancelled at startup"),
            false,
        );
    }
    Ok(())
}

pub async fn run(
    cfg: &LiveConfig,
    manifest: &StrategyManifest,
    ruleset: &Ruleset,
    guardrails: &Guardrails,
    broker: &mut Broker,
    feed: &mut AnyFeed,
) -> Result<Outcome, String> {
    let mut state = Journal::load_last(&cfg.journal_path)
        .map_err(|e| format!("journal: {e}"))?
        .unwrap_or_else(|| PortfolioState::new(guardrails.capital.base_capital_usd));
    reconcile(&mut state, broker, &cfg.repo_root).await?;

    let window = ruleset.lookback() * 2;
    let max_loss_usd =
        guardrails.capital.base_capital_usd * guardrails.limits.max_daily_loss_pct / 100.0;
    let max_position_usd =
        guardrails.capital.base_capital_usd * guardrails.limits.max_position_pct / 100.0;

    while let Some(bars) = feed.next_session().await? {
        if cfg.repo_root.join("KILL").exists() {
            emit_event(
                &cfg.repo_root,
                "warning",
                "halt_confirmed",
                "KILL present; live engine halted".into(),
                false,
            );
            return Ok(Outcome::Halted);
        }
        let date = bars[0].date.clone();
        if state.last_date.as_deref() >= Some(date.as_str()) {
            continue;
        }

        let mut last_close = BTreeMap::new();
        for bar in &bars {
            let closes = state.closes.entry(bar.symbol.clone()).or_default();
            closes.push_back(bar.close);
            while closes.len() > window.max(1) {
                closes.pop_front();
            }
            last_close.insert(bar.symbol.clone(), bar.close);
        }

        // Daily loss is marked against the previous session's closing equity
        // (at daily cadence the loss materialises between sessions).
        let prev_equity = state.equity_curve.last().copied();
        let mut orders_this_session: u32 = 0;

        for bar in &bars {
            // ---- CIRCUIT BREAKER: checked inside the order path ----
            let equity_now = state.equity(&last_close);
            if prev_equity.is_some_and(|prev| prev - equity_now >= max_loss_usd) {
                return circuit_break(cfg, &mut state, broker, &last_close, &date).await;
            }

            let weight = ruleset.target_weight(&state.closes[&bar.symbol]);
            let target_value =
                (weight * ruleset.max_position_pct / 100.0 * equity_now).min(max_position_usd); // hard cap, guardrails
            let held = state.positions.get(&bar.symbol).copied().unwrap_or(0.0);
            let delta_value = target_value - held * bar.close;
            if delta_value.abs() < MIN_TRADE_USD {
                continue;
            }
            if orders_this_session >= guardrails.limits.max_order_rate_per_min {
                emit_event(
                    &cfg.repo_root,
                    "high",
                    "order_rate_capped",
                    format!("order rate cap hit on {date}"),
                    false,
                );
                break;
            }

            let order = Order {
                client_order_id: Order::client_order_id(&manifest.id, &bar.symbol, &date),
                strategy_id: manifest.id.clone(),
                symbol: bar.symbol.clone(),
                side: if delta_value > 0.0 {
                    Side::Buy
                } else {
                    Side::Sell
                },
                qty: delta_value / bar.close,
                date: date.clone(),
            };
            // Idempotency: a journaled id is never resubmitted.
            if submitted_ids(&cfg.orders_log).contains(&order.client_order_id) {
                tracing::info!(id = %order.client_order_id, "already submitted — skipping (idempotent)");
                continue;
            }
            record_submission(&cfg.orders_log, &order.client_order_id)?;
            let fill = broker.submit(&order, bar.close).await?;
            apply_fill(&mut state, &fill);
            orders_this_session += 1;
            emit_event(
                &cfg.repo_root,
                "info",
                "fill",
                format!(
                    "{} {:?} {:.4} {} @ {:.2}",
                    fill.date, fill.side, fill.qty, fill.symbol, fill.price
                ),
                false,
            );
        }

        state.equity_curve.push(state.equity(&last_close));
        if state.first_date.is_none() {
            state.first_date = Some(date.clone());
        }
        state.last_date = Some(date);
        Journal::append(&cfg.journal_path, &state).map_err(|e| format!("journal: {e}"))?;
    }
    Ok(Outcome::Completed)
}

fn apply_fill(state: &mut PortfolioState, fill: &Fill) {
    state.cash -= fill.qty * fill.price + fill.fees;
    let pos = state.positions.entry(fill.symbol.clone()).or_insert(0.0);
    *pos += fill.qty;
    if pos.abs() < 1e-9 {
        state.positions.remove(&fill.symbol);
    }
    state.fills += 1;
}

/// Max daily loss exceeded: flatten everything, freeze, alert, drop KILL.
async fn circuit_break(
    cfg: &LiveConfig,
    state: &mut PortfolioState,
    broker: &mut Broker,
    last_close: &BTreeMap<String, f64>,
    date: &str,
) -> Result<Outcome, String> {
    tracing::error!("CIRCUIT BREAKER: max daily loss exceeded — flattening");
    let positions: Vec<(String, f64)> = state
        .positions
        .iter()
        .map(|(s, q)| (s.clone(), *q))
        .collect();
    for (symbol, qty) in positions {
        let price = last_close.get(&symbol).copied().unwrap_or(0.0);
        let order = Order {
            client_order_id: format!("flatten--{symbol}--{date}"),
            strategy_id: "circuit-breaker".into(),
            symbol: symbol.clone(),
            side: Side::Sell,
            qty: -qty,
            date: date.to_string(),
        };
        let fill = broker.submit(&order, price).await?;
        apply_fill(state, &fill);
    }
    state.equity_curve.push(state.equity(last_close));
    state.last_date = Some(date.to_string());
    Journal::append(&cfg.journal_path, state).map_err(|e| format!("journal: {e}"))?;

    std::fs::write(
        cfg.repo_root.join("KILL"),
        format!(
            "{} circuit breaker: max daily loss exceeded on {date}\n",
            chrono::Utc::now().format("%Y-%m-%dT%H:%M:%SZ")
        ),
    )
    .map_err(|e| e.to_string())?;
    emit_event(
        &cfg.repo_root,
        "critical",
        "circuit_breaker",
        format!("Max daily loss exceeded on {date}. All positions flattened, execution frozen, KILL dropped. Human /resume required."),
        true,
    );
    Ok(Outcome::CircuitBroken)
}
