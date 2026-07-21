"""Equal-weight blend of tsmom-spy-qqq and ms-shift-spy-high-displacement
(see brain/wiki/strategies/tsmom-ms-shift-blend.md).

Hypothesis: [[signal-blending]] -- rather than gating tsmom-spy-qqq with a
second, independently-computed factor that can only ever remove exposure
(as every prior follow-up in this vault did -- vol-acceleration,
vol-targeting, breadth, all of which made it worse), average its position
weight with market-structure-shift's structurally unrelated day-scale
signal (ms_shift_spy_high_displacement.py, unchanged parameters). If the
two return streams are meaningfully uncorrelated -- plausible given they
independently converged on the same headline Sharpe (0.813) via
completely different constructions -- the blend's variance should fall
faster than its expected return does, raising Sharpe versus either leg
alone.

Deliberately reuses both base signals' generate() output unmodified and
unweighted-toward-either (blend_weight=0.5, fixed a priori, not fit) --
same single-variable-follow-up discipline as every gate in this vault:
this isolates the blending question, not a re-tuning of either
component's own parameters (tsmom's lookback/skip, ms-shift's
swing_lookback/atr_period/displacement_mult all carried over unchanged).
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

_ms_shift_spec = importlib.util.spec_from_file_location(
    "ms_shift_spy_high_displacement",
    Path(__file__).resolve().parent / "ms_shift_spy_high_displacement.py",
)
_ms_shift = importlib.util.module_from_spec(_ms_shift_spec)
_ms_shift_spec.loader.exec_module(_ms_shift)


class Signal:
    def __init__(
        self,
        lookback: int = 252,
        skip: int = 21,
        swing_lookback: int = 3,
        atr_period: int = 14,
        displacement_mult: float = 2.0,
        blend_weight: float = 0.5,
    ) -> None:
        if not 0.0 <= blend_weight <= 1.0:
            raise ValueError("blend_weight must be in [0, 1]")
        self._tsmom = _tsmom.Signal(lookback, skip)
        self._ms_shift = _ms_shift.Signal(swing_lookback, atr_period, displacement_mult)
        self.blend_weight = blend_weight

    def generate(self, bars) -> pd.DataFrame:
        a = self._tsmom.generate(bars)
        b = self._ms_shift.generate(bars)
        blended = self.blend_weight * a + (1.0 - self.blend_weight) * b
        return blended[bars.columns]

    def export_params(self) -> dict:
        return {
            "type": "tsmom_ms_shift_blend",
            "lookback": self._tsmom.lookback,
            "skip": self._tsmom.skip,
            "swing_lookback": self._ms_shift.swing_lookback,
            "atr_period": self._ms_shift.atr_period,
            "displacement_mult": self._ms_shift.displacement_mult,
            "blend_weight": self.blend_weight,
        }
