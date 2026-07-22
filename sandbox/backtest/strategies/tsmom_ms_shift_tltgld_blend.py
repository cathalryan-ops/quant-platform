"""Three-way portfolio blend: tsmom-spy-qqq, ms-shift-spy-high-displacement,
and tsmom-tlt-gld (see
brain/wiki/strategies/tsmom-ms-shift-tltgld-blend.md).

Follow-up to tsmom_ms_shift_dualmom_blend.py: that 3rd-leg attempt
(dual-momentum-equity-bond-gold) turned out MORE correlated with
tsmom-spy-qqq (0.5852) than tsmom and ms-shift are with each other
(0.5522), because dual-momentum's cross-sectional ranking reuses tsmom's
own lookback=252/skip=21 logic on SPY as one of its three candidates.
tsmom-tlt-gld shares zero symbols with either existing leg and measured
near-zero standalone correlation to both (0.0051 vs tsmom, 0.0689 vs
ms-shift) -- this blend tests whether that genuine independence, despite
a weak standalone Sharpe (0.173), lifts the 3-way blend where the more
correlated-but-individually-stronger dual-momentum leg did not.

Same architecture as tsmom_ms_shift_dualmom_blend.py: composes at the
Signal level over a union universe (SPY, QQQ, TLT, GLD) so the standard
single-snapshot engine computes real netted turnover/drawdown/Sharpe from
one combined order stream. The third leg reuses tsmom_spy_qqq.Signal
directly (same class as the first leg, different column subset, no new
signal logic at all) rather than a separate implementation.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd

from backtest.signal import BarFrame

_tsmom_spec = importlib.util.spec_from_file_location(
    "tsmom_spy_qqq", Path(__file__).resolve().parent / "tsmom_spy_qqq.py"
)
_tsmom = importlib.util.module_from_spec(_tsmom_spec)
_tsmom_spec.loader.exec_module(_tsmom)

_ms_shift_spec = importlib.util.spec_from_file_location(
    "ms_shift_spy_high_displacement",
    Path(__file__).resolve().parent / "ms_shift_spy_high_displacement.py",
)
_ms_shift = importlib.util.module_from_spec(_ms_shift_spec)
_ms_shift_spec.loader.exec_module(_ms_shift)

TSMOM_COLS = ["SPY", "QQQ"]
MS_SHIFT_COLS = ["SPY", "QQQ"]
TLT_GLD_COLS = ["TLT", "GLD"]


def _subset(bars: BarFrame, cols: list[str]) -> BarFrame:
    return BarFrame(
        open=bars.open[cols], high=bars.high[cols], low=bars.low[cols], close=bars.close[cols]
    )


class Signal:
    def __init__(
        self,
        lookback: int = 252,
        skip: int = 21,
        swing_lookback: int = 3,
        atr_period: int = 14,
        displacement_mult: float = 2.0,
        tlt_gld_lookback: int = 252,
        tlt_gld_skip: int = 21,
        weight_tsmom: float = 1.0 / 3.0,
        weight_ms_shift: float = 1.0 / 3.0,
        weight_tlt_gld: float = 1.0 / 3.0,
    ) -> None:
        weights = (weight_tsmom, weight_ms_shift, weight_tlt_gld)
        if any(w < 0.0 for w in weights):
            raise ValueError("blend weights must be >= 0")
        if abs(sum(weights) - 1.0) > 1e-9:
            raise ValueError("blend weights must sum to 1.0")
        self._tsmom = _tsmom.Signal(lookback, skip)
        self._ms_shift = _ms_shift.Signal(swing_lookback, atr_period, displacement_mult)
        self._tlt_gld = _tsmom.Signal(tlt_gld_lookback, tlt_gld_skip)
        self.weight_tsmom = weight_tsmom
        self.weight_ms_shift = weight_ms_shift
        self.weight_tlt_gld = weight_tlt_gld

    def generate(self, bars: BarFrame) -> pd.DataFrame:
        a = self._tsmom.generate(_subset(bars, TSMOM_COLS))
        b = self._ms_shift.generate(_subset(bars, MS_SHIFT_COLS))
        c = self._tlt_gld.generate(_subset(bars, TLT_GLD_COLS))

        out = pd.DataFrame(0.0, index=bars.index, columns=bars.columns)
        for col in TSMOM_COLS:
            out[col] = out[col] + self.weight_tsmom * a[col]
        for col in MS_SHIFT_COLS:
            out[col] = out[col] + self.weight_ms_shift * b[col]
        for col in TLT_GLD_COLS:
            out[col] = out[col] + self.weight_tlt_gld * c[col]
        return out[bars.columns]

    def export_params(self) -> dict:
        return {
            "type": "tsmom_ms_shift_tltgld_blend",
            "lookback": self._tsmom.lookback,
            "skip": self._tsmom.skip,
            "swing_lookback": self._ms_shift.swing_lookback,
            "atr_period": self._ms_shift.atr_period,
            "displacement_mult": self._ms_shift.displacement_mult,
            "tlt_gld_lookback": self._tlt_gld.lookback,
            "tlt_gld_skip": self._tlt_gld.skip,
            "weight_tsmom": self.weight_tsmom,
            "weight_ms_shift": self.weight_ms_shift,
            "weight_tlt_gld": self.weight_tlt_gld,
        }
