"""52-week-high proximity on SPY/QQQ (see
brain/wiki/strategies/52wk-high-spy-qqq.md).

Hypothesis: [[fifty-two-week-high-effect]] (George & Hwang 2004) -- price
proximity to its own trailing 252-session high predicts near-term
continuation, via an anchoring-bias mechanism distinct from
[[time-series-momentum]]'s information-diffusion story. Structurally
different arithmetic from every prior strategy in this vault: this
signal is a ratio against a rolling MAX, not a trailing return, not a
swing/displacement break, and not a realized-vol statistic.

Long-only (v1 protocol constraint): long while today's close is within
`nearness_threshold` of its own trailing `lookback`-session high, flat
otherwise. No holding-period state machine, same style as
tsmom_spy_qqq.py -- the weight on day T is a pure function of bars[<=T]
recomputed fresh every day.
"""

from __future__ import annotations

import pandas as pd


class Signal:
    def __init__(self, lookback: int = 252, nearness_threshold: float = 0.95) -> None:
        if lookback < 2:
            raise ValueError("lookback must be >= 2")
        if not (0.0 < nearness_threshold <= 1.0):
            raise ValueError("nearness_threshold must be in (0, 1]")
        self.lookback = lookback
        self.nearness_threshold = nearness_threshold

    def generate(self, bars) -> pd.DataFrame:
        close = bars.close
        # rolling_max(t) includes today's own close -- knowable by end of
        # day T, same as every other same-day close reference in this
        # vault (e.g. ms_shift_spy's displacement check).
        rolling_max = close.rolling(window=self.lookback, min_periods=self.lookback).max()
        nearness = close / rolling_max
        weights = (nearness >= self.nearness_threshold).astype(float)
        return weights[bars.columns]

    def export_params(self) -> dict:
        return {
            "type": "high52",
            "lookback": self.lookback,
            "nearness_threshold": self.nearness_threshold,
        }
