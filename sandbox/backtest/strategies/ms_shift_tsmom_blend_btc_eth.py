"""Equal-weight blend of ms-shift-btc-eth and tsmom-btc-eth (see
brain/wiki/strategies/ms-shift-tsmom-blend-btc-eth.md).

Crypto-native analog of tsmom_ms_shift_blend.py: same "average two
structurally independent signals' position weights" premise
([[signal-blending]]), same universe both legs already operate on
(BTC/USD, ETH/USD, no union-universe composition needed since both legs
already share the same two symbols), blend_weight=0.5 fixed a priori.

Motivated directly by ms-shift-btc-eth's falsification check: correlation
to tsmom-btc-eth is 0.4319 and raw signal agreement is only 45.9-50.4%,
a stronger independence signature than the equity blend's own legs had
(0.5522 correlation) -- this tests whether that translates into the same
kind of Sharpe lift the equity blend showed.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd

_ms_shift_spec = importlib.util.spec_from_file_location(
    "ms_shift_spy_high_displacement",
    Path(__file__).resolve().parent / "ms_shift_spy_high_displacement.py",
)
_ms_shift = importlib.util.module_from_spec(_ms_shift_spec)
_ms_shift_spec.loader.exec_module(_ms_shift)

_tsmom_spec = importlib.util.spec_from_file_location(
    "tsmom_btc_eth", Path(__file__).resolve().parent / "tsmom_btc_eth.py"
)
_tsmom = importlib.util.module_from_spec(_tsmom_spec)
_tsmom_spec.loader.exec_module(_tsmom)


class Signal:
    def __init__(
        self,
        swing_lookback: int = 3,
        atr_period: int = 14,
        displacement_mult: float = 2.0,
        lookback: int = 365,
        skip: int = 30,
        blend_weight: float = 0.5,
    ) -> None:
        if not 0.0 <= blend_weight <= 1.0:
            raise ValueError("blend_weight must be in [0, 1]")
        self._ms_shift = _ms_shift.Signal(swing_lookback, atr_period, displacement_mult)
        self._tsmom = _tsmom.Signal(lookback, skip)
        self.blend_weight = blend_weight

    def generate(self, bars) -> pd.DataFrame:
        a = self._ms_shift.generate(bars)
        b = self._tsmom.generate(bars)
        blended = self.blend_weight * a + (1.0 - self.blend_weight) * b
        return blended[bars.columns]

    def export_params(self) -> dict:
        return {
            "type": "ms_shift_tsmom_blend_btc_eth",
            "swing_lookback": self._ms_shift.swing_lookback,
            "atr_period": self._ms_shift.atr_period,
            "displacement_mult": self._ms_shift.displacement_mult,
            "lookback": self._tsmom.lookback,
            "skip": self._tsmom.skip,
            "blend_weight": self.blend_weight,
        }
