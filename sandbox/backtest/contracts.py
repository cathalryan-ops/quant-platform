"""Typed mirrors of contracts/*.schema.json (all v1.0.0).

The schema files are the source of truth. Keep these models in lockstep;
a breaking change means a new schema version (new $id), never mutation.
extra="forbid" mirrors the schemas' additionalProperties: false.

Constraints the models cannot carry (runtime-enforced):
- market "crypto" is enabled in v1 (24/7 spot pairs; engine.py annualizes
  with 365 sessions/year instead of us_equities' 252 — see
  engine.SESSIONS_PER_YEAR).
- market "polymarket" is schema-valid but must be rejected by every v1
  runtime component.
- risk.max_position_pct must not exceed the guardrails.toml cap.
- A promotion with to_stage "live" must have a fully populated
  human_approval (both message ids + timestamp) — re-verify before acting.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "1.0.0"

Market = Literal["us_equities", "crypto", "polymarket"]
Family = Literal["ms_shift", "swing"]
Lifecycle = Literal["research", "backtest", "paper", "live", "retired"]
Severity = Literal["info", "warning", "high", "critical"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SignalSpec(StrictModel):
    language: Literal["python"]
    entrypoint: str


class RiskSpec(StrictModel):
    max_position_pct: float = Field(gt=0, le=100)
    stop_loss_pct: float = Field(gt=0)
    stop_loss_cooldown_sessions: int = Field(default=0, ge=0)


class Scorecard(StrictModel):
    sharpe_wf: Optional[float]
    sortino_wf: Optional[float]
    max_drawdown_bt: Optional[float]
    sharpe_paper: Optional[float]
    max_drawdown_paper: Optional[float]
    pnl_live: Optional[float]
    rank: Optional[int] = Field(ge=1)


class StrategyManifest(StrictModel):
    schema_version: Literal["1.0.0"]
    id: str = Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")
    wiki_page: str
    market: Market
    family: Family
    universe: list[str] = Field(min_length=1)
    hypothesis: str = Field(min_length=1)
    signal_spec: SignalSpec
    risk: RiskSpec
    lifecycle: Lifecycle
    scorecard: Scorecard


class DatePeriod(StrictModel):
    start: str
    end: str


class SlippageAssumptions(StrictModel):
    model: str
    bps: float = Field(ge=0)


class DataSnapshot(StrictModel):
    parquet_path: str
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    source_feed: str
    period: DatePeriod


class BacktestMetrics(StrictModel):
    sharpe: float
    sortino: float
    max_drawdown_pct: float = Field(ge=0)
    turnover: float = Field(ge=0)


class BacktestResult(StrictModel):
    schema_version: Literal["1.0.0"]
    strategy_id: str = Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")
    period: DatePeriod
    metrics: BacktestMetrics
    slippage: SlippageAssumptions
    equity_curve_path: str
    data_snapshot: DataSnapshot
    passed_thresholds: bool
    notes: str
    generated_at: str


class PaperMetrics(StrictModel):
    sharpe: float
    sortino: float
    max_drawdown_pct: float = Field(ge=0)
    pnl_usd: float
    num_trades: int = Field(ge=0)


class PaperResult(StrictModel):
    schema_version: Literal["1.0.0"]
    strategy_id: str = Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")
    period: DatePeriod
    metrics: PaperMetrics
    slippage: SlippageAssumptions
    equity_curve_path: str
    data_snapshot: DataSnapshot
    passed_thresholds: bool
    notes: str
    generated_at: str


class HumanApproval(StrictModel):
    required: bool
    telegram_msg_id: Optional[int]
    confirmation_msg_id: Optional[int]
    approved_at: Optional[str]

    def is_complete(self) -> bool:
        """A live promotion may only act on a complete two-step approval."""
        return (
            self.required
            and self.telegram_msg_id is not None
            and self.confirmation_msg_id is not None
            and self.approved_at is not None
        )


class Promotion(StrictModel):
    schema_version: Literal["1.0.0"]
    id: str = Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")
    strategy_id: str = Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")
    from_stage: Lifecycle
    to_stage: Lifecycle
    evidence: list[str]
    rationale: str = Field(min_length=1)
    issued_at: str
    human_approval: HumanApproval


class Event(StrictModel):
    schema_version: Literal["1.0.0"]
    id: str = Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")
    source_agent: str = Field(min_length=1)
    severity: Severity
    kind: str = Field(min_length=1)
    payload: dict[str, Any]
    requires_reply: bool
    ts: str
