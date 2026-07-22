"""Time-series (absolute) momentum on BTC/USD, ETH/USD (see
brain/wiki/strategies/tsmom-btc-eth.md).

Deliberately reuses tsmom_spy_qqq.Signal's `generate()` logic unmodified --
same trailing-return-sign momentum computation, same long-only/no-state-
machine construction, same "reuse a proven mechanism, don't invent a new
one" discipline as tsmom_vol_accel.py and every other tsmom follow-up in
this vault. The only change is the calendar-unit conversion this data
genuinely requires: tsmom_spy_qqq's lookback=252/skip=21 are BAR counts
that read as "12 months / 1 month" only because equity data has ~252
trading sessions/year. Alpaca's crypto snapshot has a bar for every
calendar day (24/7 spot trading, no weekend/holiday gaps -- confirmed:
1461 bars over exactly 4 calendar years), so reusing the literal integers
252/21 unchanged would silently shrink the window to ~8.3 calendar months
skipping ~3 weeks, a DIFFERENT signal than the one that was tested on
equities, not the same mechanism carried over. lookback=365/skip=30
preserves the actual "trailing 12 months, skip the most recent month"
academic construction this vault's tsmom-spy-qqq result validated --
fixed at these calendar-equivalent values a priori, not searched.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd

_tsmom_spec = importlib.util.spec_from_file_location(
    "tsmom_spy_qqq", Path(__file__).resolve().parent / "tsmom_spy_qqq.py"
)
_tsmom = importlib.util.module_from_spec(_tsmom_spec)
_tsmom_spec.loader.exec_module(_tsmom)


class Signal:
    def __init__(self, lookback: int = 365, skip: int = 30) -> None:
        self._base = _tsmom.Signal(lookback=lookback, skip=skip)
        self.lookback = lookback
        self.skip = skip

    def generate(self, bars) -> pd.DataFrame:
        return self._base.generate(bars)

    def export_params(self) -> dict:
        return {"type": "tsmom_btc_eth", "lookback": self.lookback, "skip": self.skip}
