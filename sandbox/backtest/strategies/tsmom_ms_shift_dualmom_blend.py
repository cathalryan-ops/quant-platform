"""Three-way portfolio blend: tsmom-spy-qqq, ms-shift-spy-high-displacement,
and dual-momentum-equity-bond-gold (see
brain/wiki/strategies/tsmom-ms-shift-dualmom-blend.md).

Hypothesis: [[tsmom-ms-shift-blend]] (2-leg, SPY/QQQ only) beat both its
legs by averaging two structurally independent, moderately-correlated
(0.5522) signals. Every prior third-leg candidate reused from this vault
was ruled out before implementation (see this strategy's wiki page): the
other SPY/QQQ-universe strategies are either gated variants of tsmom/
ms-shift themselves (correlated by construction) or confirmed
mechanism-level nulls (mean-reversion, turn-of-month) that would dilute
rather than diversify. dual-momentum-equity-bond-gold is the one
already-tested strategy with BOTH a real (non-null) mechanism -- its own
falsification test confirmed the cash floor and cross-asset rotation
genuinely bind -- AND exposure to a fundamentally different risk source
(TLT/GLD) that neither existing leg can reach.

Architecture: rather than a post-hoc weighted sum of three independently-
computed return series (which can't account for shared-symbol position
netting, e.g. tsmom and ms-shift both wanting SPY exposure on the same
day), this composes at the Signal level like tsmom_ms_shift_blend.py does,
extended to a UNION universe (SPY, QQQ, TLT, GLD) so the whole thing runs
through the standard single-snapshot engine path and vectorbt computes
real netted turnover/drawdown/Sharpe from one combined order stream, not
an approximation. Each leg sees only its own column subset of bars;
outputs are combined with fixed weight 1/3 each (extending the 2-leg
blend's equal-split discipline symmetrically, not fit) onto the shared
4-column output.
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

_dual_mom_spec = importlib.util.spec_from_file_location(
    "dual_momentum_equity_bond_gold",
    Path(__file__).resolve().parent / "dual_momentum_equity_bond_gold.py",
)
_dual_mom = importlib.util.module_from_spec(_dual_mom_spec)
_dual_mom_spec.loader.exec_module(_dual_mom)

TSMOM_COLS = ["SPY", "QQQ"]
MS_SHIFT_COLS = ["SPY", "QQQ"]
DUAL_MOM_COLS = ["SPY", "TLT", "GLD"]


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
        dual_mom_lookback: int = 252,
        dual_mom_skip: int = 21,
        weight_tsmom: float = 1.0 / 3.0,
        weight_ms_shift: float = 1.0 / 3.0,
        weight_dual_mom: float = 1.0 / 3.0,
    ) -> None:
        weights = (weight_tsmom, weight_ms_shift, weight_dual_mom)
        if any(w < 0.0 for w in weights):
            raise ValueError("blend weights must be >= 0")
        if abs(sum(weights) - 1.0) > 1e-9:
            raise ValueError("blend weights must sum to 1.0")
        self._tsmom = _tsmom.Signal(lookback, skip)
        self._ms_shift = _ms_shift.Signal(swing_lookback, atr_period, displacement_mult)
        self._dual_mom = _dual_mom.Signal(dual_mom_lookback, dual_mom_skip)
        self.weight_tsmom = weight_tsmom
        self.weight_ms_shift = weight_ms_shift
        self.weight_dual_mom = weight_dual_mom

    def generate(self, bars: BarFrame) -> pd.DataFrame:
        a = self._tsmom.generate(_subset(bars, TSMOM_COLS))
        b = self._ms_shift.generate(_subset(bars, MS_SHIFT_COLS))
        c = self._dual_mom.generate(_subset(bars, DUAL_MOM_COLS))

        out = pd.DataFrame(0.0, index=bars.index, columns=bars.columns)
        for col in TSMOM_COLS:
            out[col] = out[col] + self.weight_tsmom * a[col]
        for col in MS_SHIFT_COLS:
            out[col] = out[col] + self.weight_ms_shift * b[col]
        for col in DUAL_MOM_COLS:
            out[col] = out[col] + self.weight_dual_mom * c[col]
        return out[bars.columns]

    def export_params(self) -> dict:
        return {
            "type": "tsmom_ms_shift_dualmom_blend",
            "lookback": self._tsmom.lookback,
            "skip": self._tsmom.skip,
            "swing_lookback": self._ms_shift.swing_lookback,
            "atr_period": self._ms_shift.atr_period,
            "displacement_mult": self._ms_shift.displacement_mult,
            "dual_mom_lookback": self._dual_mom.lookback,
            "dual_mom_skip": self._dual_mom.skip,
            "weight_tsmom": self.weight_tsmom,
            "weight_ms_shift": self.weight_ms_shift,
            "weight_dual_mom": self.weight_dual_mom,
        }
