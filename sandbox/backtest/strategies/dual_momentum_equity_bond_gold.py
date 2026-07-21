"""Dual momentum across equities, bonds, and gold (see
brain/wiki/strategies/dual-momentum-equity-bond-gold.md).

Hypothesis: [[dual-momentum]] -- combine [[time-series-momentum]]'s
absolute floor (is the leader's own trailing trend positive?) with
[[cross-sectional-momentum]]'s relative rank (which of SPY/TLT/GLD is
winning?). Structurally distinct from sector_rotation.py: that signal
always holds *something* (the least-bad of 10 sectors), because every
candidate is the same asset class; this one can go fully flat, because
the basket spans genuinely different risk regimes and the absolute floor
is the mechanism that lets "nothing looks good right now" be expressible.

Monthly rebalance, same detection pattern as sector_rotation.py
(backward-only calendar comparison -- causal by construction). On each
rebalance day, rank SPY/TLT/GLD (or whatever `bars.columns` is) by
trailing 12-1 momentum (lookback=252, skip=21 -- unchanged from
tsmom_spy_qqq.py and sector_rotation.py for direct comparability). Hold
the single highest-momentum asset, equal-weighted at 1.0, but ONLY if its
own momentum is positive; otherwise flat until the next rebalance finds a
qualifying leader.
"""

from __future__ import annotations

import pandas as pd


class Signal:
    def __init__(self, lookback: int = 252, skip: int = 21) -> None:
        if lookback < 2:
            raise ValueError("lookback must be >= 2")
        if skip < 0 or skip >= lookback:
            raise ValueError("skip must be >= 0 and < lookback")
        self.lookback = lookback
        self.skip = skip

    def generate(self, bars) -> pd.DataFrame:
        close = bars.close
        symbols = list(bars.columns)

        momentum = close.shift(self.skip) / close.shift(self.skip + self.lookback) - 1.0

        weights = pd.DataFrame(0.0, index=bars.index, columns=symbols)
        current_selection: str | None = None
        prev_period: tuple[int, int] | None = None
        for t, date in enumerate(bars.index):
            period = (date.year, date.month)
            is_rebalance_day = period != prev_period
            prev_period = period
            if is_rebalance_day:
                row = momentum.iloc[t]
                if row.notna().all():
                    best = row.idxmax()
                    current_selection = best if row[best] > 0.0 else None
                else:
                    current_selection = None  # not enough history yet -- stay flat
            if current_selection is not None:
                weights.loc[date, current_selection] = 1.0
        return weights[bars.columns]

    def export_params(self) -> dict:
        return {
            "type": "dual_momentum",
            "lookback": self.lookback,
            "skip": self.skip,
        }
