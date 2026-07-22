"""Cross-sectional momentum on the 50-single-name-stock universe (see
brain/wiki/strategies/cross-sectional-momentum-stocks50.md).

Deliberately reuses sector_rotation.Signal's generate() logic completely
unmodified -- identical rank-by-trailing-12-1-momentum-and-hold-the-top-N
mechanism already tested on the 10 SPDR sector ETFs
([[sector-rotation]]). The only change is top_n: sector-rotation held the
top 3 of 10 (~30% concentration); this universe has 50 names, so top_n=15
preserves the same ~30% concentration level rather than reusing the
literal integer 3, which would be a ~6% cut on this universe -- a
different (much more concentrated) bet, not the same mechanism carried
over. lookback=252/skip=21 unchanged, same values as every prior
momentum strategy in this vault (tsmom-spy-qqq, sector-rotation), for
direct comparability. top_n=15 fixed a priori by the concentration-ratio
argument above, not searched.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd

_sector_rotation_spec = importlib.util.spec_from_file_location(
    "sector_rotation", Path(__file__).resolve().parent / "sector_rotation.py"
)
_sector_rotation = importlib.util.module_from_spec(_sector_rotation_spec)
_sector_rotation_spec.loader.exec_module(_sector_rotation)


class Signal:
    def __init__(self, lookback: int = 252, skip: int = 21, top_n: int = 15) -> None:
        self._base = _sector_rotation.Signal(lookback=lookback, skip=skip, top_n=top_n)
        self.lookback = lookback
        self.skip = skip
        self.top_n = top_n

    def generate(self, bars) -> pd.DataFrame:
        return self._base.generate(bars)

    def export_params(self) -> dict:
        return {
            "type": "cross_sectional_momentum_stocks50",
            "lookback": self.lookback,
            "skip": self.skip,
            "top_n": self.top_n,
        }
