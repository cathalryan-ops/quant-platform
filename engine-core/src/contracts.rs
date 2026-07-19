//! Typed mirrors of `contracts/*.schema.json` (all v1.0.0).
//!
//! The schema files are the source of truth. Keep these types in lockstep;
//! a breaking change means a new schema version (new `$id`), never mutation.
//! `deny_unknown_fields` mirrors the schemas' `additionalProperties: false`.
//!
//! Constraints the type system cannot carry (runtime-enforced):
//! - `Market::Polymarket` is schema-valid but must be rejected by every v1
//!   runtime component.
//! - `risk.max_position_pct` must not exceed the `guardrails.toml` cap.
//! - A promotion with `to_stage: live` must have a fully populated
//!   `human_approval` (both message ids + timestamp) — re-verify before acting.

use schemars::JsonSchema;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum Market {
    UsEquities,
    /// Reserved for v2 — rejected by all v1 runtime components.
    Polymarket,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum Family {
    MsShift,
    Swing,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum Lifecycle {
    Research,
    Backtest,
    Paper,
    Live,
    Retired,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum Severity {
    Info,
    Warning,
    High,
    Critical,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct SignalSpec {
    /// Always "python" in v1.
    pub language: String,
    /// `module_path.py:ClassName` implementing the Signal protocol.
    pub entrypoint: String,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct RiskSpec {
    pub max_position_pct: f64,
    pub stop_loss_pct: f64,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct Scorecard {
    pub sharpe_wf: Option<f64>,
    pub sortino_wf: Option<f64>,
    pub max_drawdown_bt: Option<f64>,
    pub sharpe_paper: Option<f64>,
    pub max_drawdown_paper: Option<f64>,
    pub pnl_live: Option<f64>,
    pub rank: Option<u32>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct StrategyManifest {
    pub schema_version: String,
    pub id: String,
    pub wiki_page: String,
    pub market: Market,
    pub family: Family,
    pub universe: Vec<String>,
    pub hypothesis: String,
    pub signal_spec: SignalSpec,
    pub risk: RiskSpec,
    pub lifecycle: Lifecycle,
    pub scorecard: Scorecard,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct DatePeriod {
    /// ISO 8601 date (YYYY-MM-DD).
    pub start: String,
    pub end: String,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct SlippageAssumptions {
    pub model: String,
    pub bps: f64,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct DataSnapshot {
    pub parquet_path: String,
    /// `sha256:<64 hex chars>` of the parquet file.
    pub content_hash: String,
    pub source_feed: String,
    pub period: DatePeriod,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct BacktestMetrics {
    pub sharpe: f64,
    pub sortino: f64,
    pub max_drawdown_pct: f64,
    pub turnover: f64,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct BacktestResult {
    pub schema_version: String,
    pub strategy_id: String,
    pub period: DatePeriod,
    pub metrics: BacktestMetrics,
    pub slippage: SlippageAssumptions,
    pub equity_curve_path: String,
    pub data_snapshot: DataSnapshot,
    pub passed_thresholds: bool,
    pub notes: String,
    /// RFC 3339 timestamp.
    pub generated_at: String,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct PaperMetrics {
    pub sharpe: f64,
    pub sortino: f64,
    pub max_drawdown_pct: f64,
    pub pnl_usd: f64,
    pub num_trades: u32,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct PaperResult {
    pub schema_version: String,
    pub strategy_id: String,
    pub period: DatePeriod,
    pub metrics: PaperMetrics,
    pub slippage: SlippageAssumptions,
    pub equity_curve_path: String,
    pub data_snapshot: DataSnapshot,
    pub passed_thresholds: bool,
    pub notes: String,
    pub generated_at: String,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct HumanApproval {
    pub required: bool,
    pub telegram_msg_id: Option<i64>,
    pub confirmation_msg_id: Option<i64>,
    pub approved_at: Option<String>,
}

impl HumanApproval {
    /// A live promotion may only act on a complete two-step approval.
    pub fn is_complete(&self) -> bool {
        self.required
            && self.telegram_msg_id.is_some()
            && self.confirmation_msg_id.is_some()
            && self.approved_at.is_some()
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct Promotion {
    pub schema_version: String,
    pub id: String,
    pub strategy_id: String,
    pub from_stage: Lifecycle,
    pub to_stage: Lifecycle,
    pub evidence: Vec<String>,
    pub rationale: String,
    pub issued_at: String,
    pub human_approval: HumanApproval,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct Event {
    pub schema_version: String,
    pub id: String,
    pub source_agent: String,
    pub severity: Severity,
    pub kind: String,
    pub payload: serde_json::Value,
    pub requires_reply: bool,
    pub ts: String,
}
