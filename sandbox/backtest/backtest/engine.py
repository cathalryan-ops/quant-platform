"""Walk-forward backtest engine.

Deterministic by construction: same manifest + same pinned snapshot =>
byte-identical metrics (generated_at is the only field allowed to differ
between runs). Decision on day T is executed on day T+1 (weights shifted);
the lookahead guard in signal.py additionally proves the signal itself
doesn't peek. The manifest's risk.stop_loss_pct is enforced here as a
portfolio-level overlay (see risk.py) applied on top of the signal's raw
weights — deliberately kept out of Signal.generate() so the ADR-0002
Python<->Rust golden-test parity (which pins the raw signal decision) is
unaffected by risk-control changes."""

from __future__ import annotations

import datetime as dt
import json
import tomllib
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from contracts import (
    BacktestMetrics,
    BacktestResult,
    DataSnapshot,
    DatePeriod,
    SlippageAssumptions,
    StrategyManifest,
)

from .data import Snapshot, bar_frame, close_matrix, default_snapshot_path, load_snapshot
from .oos import check_out_of_sample
from .risk import apply_stop_loss
from .signal import generate_checked, load_signal
from .thresholds import BacktestThresholds

TRADING_DAYS = 252
SLIPPAGE_BPS = 5.0
FEE_PCT = 0.0005  # 5 bps commission assumption per side


class ManifestRejected(ValueError):
    """Manifest violates a runtime rule (market, guardrail cap, lifecycle)."""


@dataclass(frozen=True)
class Guardrails:
    base_capital_usd: float
    max_position_pct: float

    @classmethod
    def load(cls, path: Path) -> "Guardrails":
        with open(path, "rb") as f:
            raw = tomllib.load(f)
        return cls(
            base_capital_usd=raw["capital"]["base_capital_usd"],
            max_position_pct=raw["limits"]["max_position_pct"],
        )


def find_repo_root(start: Path) -> Path:
    for candidate in [start, *start.parents]:
        if (candidate / "contracts").is_dir() and (candidate / "CLAUDE.md").is_file():
            return candidate
    raise FileNotFoundError(f"no repo root above {start}")


def validate_manifest(manifest: StrategyManifest, guardrails: Guardrails) -> None:
    if manifest.market != "us_equities":
        raise ManifestRejected(f"market {manifest.market!r} is not enabled in v1")
    if manifest.risk.max_position_pct > guardrails.max_position_pct:
        raise ManifestRejected(
            f"risk.max_position_pct {manifest.risk.max_position_pct} exceeds "
            f"guardrail cap {guardrails.max_position_pct}"
        )


def _annualized_sharpe(returns: np.ndarray) -> float:
    if len(returns) < 2 or returns.std(ddof=1) == 0.0:
        return 0.0
    return float(returns.mean() / returns.std(ddof=1) * np.sqrt(TRADING_DAYS))


def _annualized_sortino(returns: np.ndarray) -> float:
    downside = np.sqrt(np.mean(np.square(np.minimum(returns, 0.0))))
    if len(returns) < 2 or downside == 0.0:
        return 0.0
    return float(returns.mean() / downside * np.sqrt(TRADING_DAYS))


def _oos_note(oos_check, oos_fraction: float, oos_reject_threshold: float) -> str:
    verdict = "PASSED" if oos_check.passed else "REJECTED"
    degradation = (
        "no positive in-sample edge (Sharpe <= 0), OOS not meaningfully comparable"
        if oos_check.degradation_pct == float("inf")
        else f"{oos_check.degradation_pct:+.1%} degradation vs {oos_reject_threshold:.0%} threshold"
    )
    return (
        f" OOS holdout (trailing {oos_fraction:.0%}, split {oos_check.split_date}): "
        f"in-sample Sharpe {oos_check.in_sample_sharpe}, OOS Sharpe {oos_check.oos_sharpe} "
        f"({degradation}) — {verdict}."
    )


def _walk_forward(returns: pd.Series, folds: int) -> tuple[float, float, list[float]]:
    fold_sharpes: list[float] = []
    fold_sortinos: list[float] = []
    for chunk in np.array_split(returns.to_numpy(), folds):
        fold_sharpes.append(_annualized_sharpe(chunk))
        fold_sortinos.append(_annualized_sortino(chunk))
    return float(np.mean(fold_sharpes)), float(np.mean(fold_sortinos)), fold_sharpes


def run_backtest(
    manifest: StrategyManifest,
    *,
    start: str,
    end: str,
    repo_root: Path,
    snapshot_path: Path | None = None,
    expected_hash: str | None = None,
    folds: int = 5,
    out_dir: Path | None = None,
    fetch: bool = True,
    source_feed: str = "alpaca_iex_daily",
    oos_fraction: float = 0.0,
    oos_reject_threshold: float = 0.35,
) -> Path:
    """Run one walk-forward backtest; returns the path of the written result JSON.

    `oos_fraction` (default 0.0, disabled) reserves the trailing fraction of
    sessions as an out-of-sample holdout untouched by whatever process
    chose this manifest's parameters — see oos.py. When enabled, a
    configuration whose OOS Sharpe degrades by more than
    `oos_reject_threshold` (fractional, default 0.35 = 35%) relative to its
    in-sample Sharpe fails `passed_thresholds` regardless of the ordinary
    walk-forward metrics, and the split is recorded in `notes`.
    """
    import vectorbt as vbt

    guardrails = Guardrails.load(repo_root / "live" / "guardrails.toml")
    validate_manifest(manifest, guardrails)

    if snapshot_path is None:
        snapshot_path = default_snapshot_path(
            repo_root / "data", list(manifest.universe), start, end
        )
    snapshot: Snapshot = load_snapshot(
        snapshot_path,
        universe=list(manifest.universe),
        start=start,
        end=end,
        source_feed=source_feed,
        expected_hash=expected_hash,
        fetch=fetch,
    )
    bars = bar_frame(snapshot, list(manifest.universe))
    close = bars.close

    signal = load_signal(
        manifest.signal_spec.entrypoint, root=Path(__file__).resolve().parents[1]
    )
    weights = generate_checked(signal, bars)

    # Decision on T executes on T+1; apply the manifest's stop-loss overlay
    # in execution-timeline space, then scale to the per-position cap.
    shifted = weights.shift(1).fillna(0.0)
    stopped = apply_stop_loss(
        shifted,
        close,
        bars.low,
        manifest.risk.stop_loss_pct,
        manifest.risk.stop_loss_cooldown_sessions,
    )
    target = (stopped * manifest.risk.max_position_pct / 100.0).astype(np.float64)

    pf = vbt.Portfolio.from_orders(
        close,
        size=target,
        size_type="targetpercent",
        group_by=True,
        cash_sharing=True,
        fees=FEE_PCT,
        slippage=SLIPPAGE_BPS / 10_000,
        init_cash=guardrails.base_capital_usd,
        freq="1D",
    )

    returns = pf.returns()
    wf_sharpe, wf_sortino, fold_sharpes = _walk_forward(returns, folds)
    max_dd_pct = float(abs(pf.max_drawdown()) * 100.0)
    oos_check = (
        check_out_of_sample(returns, oos_fraction, oos_reject_threshold)
        if oos_fraction > 0.0
        else None
    )

    orders = pf.orders.records_readable
    total_traded = float((orders["Size"].abs() * orders["Price"]).sum())
    years = len(close) / TRADING_DAYS
    turnover = float(total_traded / (float(pf.value().mean()) * years)) if years > 0 else 0.0

    thresholds = BacktestThresholds.load(
        repo_root / "contracts" / "promotion_thresholds.toml"
    )
    metrics = BacktestMetrics(
        sharpe=round(wf_sharpe, 6),
        sortino=round(wf_sortino, 6),
        max_drawdown_pct=round(max_dd_pct, 6),
        turnover=round(turnover, 6),
    )

    out_dir = (out_dir or repo_root / "data" / "results") / manifest.id
    out_dir.mkdir(parents=True, exist_ok=True)
    equity_png = out_dir / "backtest_equity.png"
    _plot_equity(pf.value(), manifest.id, equity_png)

    result = BacktestResult(
        schema_version="1.0.0",
        strategy_id=manifest.id,
        period=DatePeriod(start=start, end=end),
        metrics=metrics,
        slippage=SlippageAssumptions(model="fixed_bps", bps=SLIPPAGE_BPS),
        equity_curve_path=str(
            equity_png.relative_to(repo_root)
            if equity_png.is_relative_to(repo_root)
            else equity_png
        ),
        data_snapshot=DataSnapshot(
            parquet_path=str(snapshot.path.relative_to(repo_root))
            if snapshot.path.is_relative_to(repo_root)
            else str(snapshot.path),
            content_hash=snapshot.content_hash,
            source_feed=snapshot.source_feed,
            period=DatePeriod(start=start, end=end),
        ),
        passed_thresholds=(
            thresholds.passed(
                sharpe=metrics.sharpe,
                sortino=metrics.sortino,
                max_drawdown_pct=metrics.max_drawdown_pct,
            )
            and (oos_check.passed if oos_check is not None else True)
        ),
        notes=(
            f"{folds} walk-forward folds; fold Sharpes "
            f"{[round(s, 3) for s in fold_sharpes]}; fees {FEE_PCT * 1e4:.0f} bps, "
            f"slippage {SLIPPAGE_BPS:.0f} bps; decisions execute next session."
            + (_oos_note(oos_check, oos_fraction, oos_reject_threshold) if oos_check is not None else "")
        ),
        generated_at=dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )

    result_path = out_dir / "backtest_result.json"
    result_path.write_text(result.model_dump_json(indent=2) + "\n")

    # ADR 0002: export the fitted signal as a parameterised ruleset for the
    # Rust paper/live engines, with the snapshot provenance of the fit.
    params = getattr(signal, "export_params", lambda: None)()
    if params is not None:
        ruleset = {
            "schema_version": "1.0.0",
            "strategy_id": manifest.id,
            "family": manifest.family,
            "max_position_pct": manifest.risk.max_position_pct,
            "params": params,
            "data_snapshot": result.data_snapshot.model_dump(),
        }
        (out_dir / "ruleset.json").write_text(json.dumps(ruleset, indent=2) + "\n")
    return result_path


def _plot_equity(value: pd.Series, strategy_id: str, path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(value.index, value.to_numpy())
    ax.set_title(f"{strategy_id} — backtest equity")
    ax.set_ylabel("Portfolio value (USD)")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
