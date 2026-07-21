"""Cross-sectional sector rotation among the 10 SPDR sector ETFs (see
brain/wiki/strategies/sector-rotation.md).

Hypothesis: [[cross-sectional-momentum]] -- ranking assets against EACH
OTHER's trailing return, not against their own history in isolation
([[time-series-momentum]]'s absolute construction), and rotating into the
relative leaders. First genuinely cross-sectional strategy in this
vault -- every prior strategy scored each symbol independently against
its own past; this one can only be expressed with a basket to rank
against, which is exactly what the wider 16-symbol snapshot exists for.

Monthly rebalance: on the first trading day of each calendar month, rank
all `bars.columns` symbols by trailing 12-1 momentum (lookback=252,
skip=21 trading days -- same construction and values as
tsmom_spy_qqq.py, for direct comparability against the absolute-momentum
result already on record) using data through that day, and hold the top
`top_n` equal-weighted until the next rebalance.

Rebalance-day detection is purely backward-looking: it compares each
day's calendar month against the PREVIOUS day's, never a future day, so
a truncated run agrees with the full-history run at every point in
common -- causal by construction, not by convention.
"""

from __future__ import annotations

import pandas as pd


class Signal:
    def __init__(self, lookback: int = 252, skip: int = 21, top_n: int = 3) -> None:
        if lookback < 2:
            raise ValueError("lookback must be >= 2")
        if skip < 0 or skip >= lookback:
            raise ValueError("skip must be >= 0 and < lookback")
        if top_n < 1:
            raise ValueError("top_n must be >= 1")
        self.lookback = lookback
        self.skip = skip
        self.top_n = top_n

    def generate(self, bars) -> pd.DataFrame:
        close = bars.close
        symbols = list(bars.columns)
        if self.top_n > len(symbols):
            raise ValueError(f"top_n={self.top_n} exceeds universe size {len(symbols)}")

        momentum = close.shift(self.skip) / close.shift(self.skip + self.lookback) - 1.0

        weights = pd.DataFrame(0.0, index=bars.index, columns=symbols)
        current_selection: list[str] = []
        prev_period: tuple[int, int] | None = None
        for t, date in enumerate(bars.index):
            period = (date.year, date.month)
            is_rebalance_day = period != prev_period
            prev_period = period
            if is_rebalance_day:
                row = momentum.iloc[t]
                if row.notna().all():
                    current_selection = list(row.sort_values(ascending=False).index[: self.top_n])
                else:
                    current_selection = []  # not enough history yet -- stay flat
            if current_selection:
                weights.loc[date, current_selection] = 1.0
        return weights[bars.columns]

    def export_params(self) -> dict:
        return {
            "type": "sector_rotation",
            "lookback": self.lookback,
            "skip": self.skip,
            "top_n": self.top_n,
        }
