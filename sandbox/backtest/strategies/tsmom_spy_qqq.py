"""Time-series (absolute) momentum on SPY/QQQ (see
brain/wiki/strategies/tsmom-spy-qqq.md).

Hypothesis: assets that have trended up over the trailing 12 months
continue to drift up over the near term, and vice versa (Moskowitz/Ooi/
Pedersen 2012's time-series momentum). Structurally orthogonal to every
prior hypothesis in this vault: [[market-structure-shift]] and
[[displacement]] operate on single confirmed swing breaks (days), and
mean-reversion-spy-qqq operates on single-day shocks (days); this signal
has no swing/displacement/shock geometry at all and no fixed holding
period -- it holds for however long the trailing-12-month trend itself
stays positive, which is calendar-scale, not day-scale.

Standard "12-1" construction: trailing `lookback` (252 trading days ~= 12
months) return, ending `skip` (21 trading days ~= 1 month) sessions ago --
skipping the most recent month is the standard academic construction,
specifically to net out the well-documented *short-term* reversal effect
(which is the opposite-signed, days-scale phenomenon mean-reversion-spy-qqq
already tested and found no evidence for on this data).

Long-only (v1 protocol constraint): long when trailing momentum is
positive, flat otherwise. No re-entry state machine at all -- unlike
mean_reversion_spy_qqq's hold_days countdown, the weight on day T is a
pure function of bars[<=T] recomputed fresh every day (shift-based, so it
changes only when the 12-month-ending-1-month-ago return itself changes
sign -- naturally low-frequency).
"""

from __future__ import annotations

import pandas as pd


class Signal:
    def __init__(self, lookback: int = 252, skip: int = 21) -> None:
        if lookback < 2:
            raise ValueError("lookback must be >= 2")
        if skip < 0:
            raise ValueError("skip must be >= 0")
        if skip >= lookback:
            raise ValueError("skip must be < lookback")
        self.lookback = lookback
        self.skip = skip

    def generate(self, bars) -> pd.DataFrame:
        close = bars.close
        # momentum(t) = close[t-skip] / close[t-skip-lookback] - 1: a function
        # of bars strictly before t-skip+1 <= t, so this can never peek past
        # today's own bar, let alone into the future.
        lagged = close.shift(self.skip)
        base = close.shift(self.skip + self.lookback)
        momentum = lagged / base - 1.0
        weights = (momentum > 0.0).astype(float)
        return weights[bars.columns]

    def export_params(self) -> dict:
        """Fitted parameters, kept in the same shape as ms_shift's for
        ADR-0002 (Rust ruleset export), even though this strategy hasn't
        reached a stage that needs the Rust mirror yet."""
        return {"type": "tsmom", "lookback": self.lookback, "skip": self.skip}
