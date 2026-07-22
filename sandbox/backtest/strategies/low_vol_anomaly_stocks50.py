"""Low-volatility anomaly on the 50-single-name-stock universe (see
brain/wiki/strategies/low-vol-anomaly-stocks50.md).

First mechanism in this vault that is neither momentum (time-series or
cross-sectional), market-structure-shift, mean-reversion, nor calendar.
[[low-volatility-anomaly]]: rank a basket by trailing realized volatility
and hold the LEAST volatile subset, equal-weighted -- the opposite
ranking direction from every prior cross-sectional strategy here
([[sector-rotation]], [[cross-sectional-momentum-stocks50]] both rank by
trailing return and hold the strongest).

Rebalance cadence, universe, and top_n concentration are carried over
unchanged from cross-sectional-momentum-stocks50 for direct
comparability: monthly rebalance, same 50-stock universe, top_n=15
(~30% of the universe, matching sector-rotation's own 3-of-10 ratio).
lookback=252 (1 trading year) chosen to match the lookback already used
by every momentum strategy in this vault (tsmom-spy-qqq, sector-rotation,
cross-sectional-momentum-stocks50) for direct comparability, and because
252 trading days is the standard trailing window in the low-vol
literature (Ang/Hodges/Xing/Zhang 2006 use 1-year realized vol; Frazzini
& Pedersen's Betting Against Beta likewise uses a 1-year rolling window).
No `skip` gap -- unlike momentum's skip=21 (deliberately avoiding the
short-term-reversal window), there is no analogous reason to exclude the
most recent month of return data from a volatility estimate, so today's
full trailing lookback is used unmodified.

Long-only, no short leg: every cross-sectional strategy in this vault to
date is long-only; a long-(low-vol)/short-(high-vol) variant is the
natural next step in the literature (Betting Against Beta's actual
construction) but is a genuinely different risk profile and NOT
implemented here -- flagged in the wiki page as an untested follow-up,
not silently assumed.
"""

from __future__ import annotations

import pandas as pd


class Signal:
    def __init__(self, lookback: int = 252, top_n: int = 15) -> None:
        if lookback < 2:
            raise ValueError("lookback must be >= 2")
        if top_n < 1:
            raise ValueError("top_n must be >= 1")
        self.lookback = lookback
        self.top_n = top_n

    def generate(self, bars) -> pd.DataFrame:
        close = bars.close
        symbols = list(bars.columns)
        if self.top_n > len(symbols):
            raise ValueError(f"top_n={self.top_n} exceeds universe size {len(symbols)}")

        daily_ret = close.pct_change()
        realized_vol = daily_ret.rolling(self.lookback).std()

        weights = pd.DataFrame(0.0, index=bars.index, columns=symbols)
        current_selection: list[str] = []
        prev_period: tuple[int, int] | None = None
        for t, date in enumerate(bars.index):
            period = (date.year, date.month)
            is_rebalance_day = period != prev_period
            prev_period = period
            if is_rebalance_day:
                row = realized_vol.iloc[t]
                if row.notna().all():
                    # ascending: LEAST volatile first -- the opposite ranking
                    # direction from sector_rotation's momentum sort.
                    current_selection = list(row.sort_values(ascending=True).index[: self.top_n])
                else:
                    current_selection = []  # not enough history yet -- stay flat
            if current_selection:
                weights.loc[date, current_selection] = 1.0
        return weights[bars.columns]

    def export_params(self) -> dict:
        return {
            "type": "low_vol_anomaly",
            "lookback": self.lookback,
            "top_n": self.top_n,
        }
