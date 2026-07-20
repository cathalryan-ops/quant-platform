"""Out-of-sample holdout check: reserve a trailing, untuned chunk of the
backtest date range so a manifest configuration's Sharpe can be checked for
degradation "in the wild" before it's read as promotion evidence.

Deliberately narrow in scope: this splits the already-computed daily return
series by date and compares in-sample vs. held-out Sharpe for that ONE run
— it does not re-fetch data or re-run the signal/risk pipeline twice, and
it doesn't (can't) stop a human from repeatedly re-running backtests
against the same OOS window and implicitly tuning against it anyway — that
remains a process-discipline concern (see ms-shift-spy-v2's retirement
note on repeated displacement_mult tuning), not something a mechanism
alone can prevent.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

TRADING_DAYS = 252


@dataclass(frozen=True)
class OosCheck:
    split_date: str
    in_sample_sharpe: float
    oos_sharpe: float
    # Positive = OOS worse than in-sample; negative = OOS better. `inf` when
    # in-sample Sharpe <= 0 (no positive edge to degrade in the first place).
    degradation_pct: float
    passed: bool


def _annualized_sharpe(returns: np.ndarray) -> float:
    if len(returns) < 2 or returns.std(ddof=1) == 0.0:
        return 0.0
    return float(returns.mean() / returns.std(ddof=1) * np.sqrt(TRADING_DAYS))


def check_out_of_sample(
    returns: pd.Series,
    oos_fraction: float,
    reject_threshold: float = 0.35,
) -> OosCheck:
    """Split `returns` (chronological daily returns, oldest first) into a
    leading in-sample slice and a trailing out-of-sample slice, the OOS
    slice sized by `oos_fraction` (e.g. 0.2 reserves the trailing 20% of
    sessions, untouched by whatever process chose this manifest's params).

    Rejects (`passed=False`) if OOS Sharpe degrades by more than
    `reject_threshold` (fractional, e.g. the default 0.35 = 35%) relative
    to in-sample Sharpe. An in-sample Sharpe <= 0 has no positive edge to
    validate out-of-sample at all, so it always fails regardless of what
    the OOS Sharpe turns out to be.
    """
    if not 0.0 < oos_fraction < 1.0:
        raise ValueError(f"oos_fraction must be in (0, 1), got {oos_fraction}")
    if reject_threshold <= 0.0:
        raise ValueError(f"reject_threshold must be > 0, got {reject_threshold}")

    n = len(returns)
    if n < 4:
        raise ValueError(f"need at least 4 sessions to split in-sample/OOS, got {n}")
    split_idx = int(round(n * (1.0 - oos_fraction)))
    split_idx = max(1, min(split_idx, n - 1))  # keep both slices non-empty

    in_sample = returns.iloc[:split_idx]
    oos = returns.iloc[split_idx:]
    in_sample_sharpe = _annualized_sharpe(in_sample.to_numpy())
    oos_sharpe = _annualized_sharpe(oos.to_numpy())

    if in_sample_sharpe <= 0.0:
        degradation_pct = float("inf")
        passed = False
    else:
        degradation_pct = round((in_sample_sharpe - oos_sharpe) / in_sample_sharpe, 6)
        passed = degradation_pct <= reject_threshold

    return OosCheck(
        split_date=str(oos.index[0].date()),
        in_sample_sharpe=round(in_sample_sharpe, 6),
        oos_sharpe=round(oos_sharpe, 6),
        degradation_pct=degradation_pct,
        passed=passed,
    )
