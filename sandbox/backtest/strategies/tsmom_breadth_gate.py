"""Time-series momentum on SPY/QQQ, gated to sector-breadth participation
(see brain/wiki/strategies/tsmom-breadth-gate.md).

Hypothesis: [[market-breadth]] -- a rally confirmed by broad participation
(most sectors independently trending up) is more durable than one carried
by a narrow subset while the rest lag, so gating tsmom-spy-qqq's raw
long/flat signal off whenever sector participation falls below
`breadth_threshold` should filter out exactly the fragile, narrow-leadership
stretches most likely to reverse -- without touching tsmom's own lookback/
skip or re-deriving them.

Structurally different from the earlier vol-gate line (tsmom-vol-accel,
tsmom-vol-accel-hysteresis, tsmom-vol-target): those gate off a
self-referential statistic of the traded asset's OWN price series
(realized vol vs. its own baseline). This gate is cross-sectional -- it
looks at OTHER assets (the 10 SPDR sectors) entirely, only made possible by
the wider 16-symbol snapshot. Also distinct from [[cross-sectional-momentum]]
/[[dual-momentum]]: those use the cross-section to SELECT which asset to
hold; this uses it purely as a confirmation filter on an independent
absolute-momentum decision for a different asset (SPY or QQQ), never to
choose among the sectors themselves (their own weights are always zero).

Deliberately reuses tsmom_spy_qqq.Signal's generate() output unmodified,
both as the trade decision for SPY/QQQ AND, applied to the sector columns,
as each sector's own trend-up/down state -- same single-variable-follow-up
discipline as the vol-gate line: this isolates the breadth question as one
additive filter, not a re-tuning of tsmom's own parameters.
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
    def __init__(
        self,
        lookback: int = 252,
        skip: int = 21,
        breadth_threshold: float = 0.5,
        trade_symbols: tuple[str, ...] = ("SPY", "QQQ"),
    ) -> None:
        if breadth_threshold <= 0.0:
            raise ValueError("breadth_threshold must be > 0.0 (a no-op gate at <=0.0)")
        if breadth_threshold > 1.0:
            raise ValueError("breadth_threshold must be <= 1.0 (never satisfiable above 1.0)")
        if not trade_symbols:
            raise ValueError("trade_symbols must be non-empty")
        self._base = _tsmom.Signal(lookback, skip)
        self.breadth_threshold = breadth_threshold
        self.trade_symbols = tuple(trade_symbols)

    def generate(self, bars) -> pd.DataFrame:
        raw = self._base.generate(bars)  # 1.0/0.0 per symbol: that symbol's own trend state
        symbols = list(bars.columns)
        trade_symbols = [s for s in self.trade_symbols if s in symbols]
        breadth_symbols = [s for s in symbols if s not in trade_symbols]
        if not breadth_symbols:
            raise ValueError("need at least one breadth symbol distinct from trade_symbols")

        breadth_frac = raw[breadth_symbols].sum(axis=1) / len(breadth_symbols)
        gate = (breadth_frac >= self.breadth_threshold).astype(float)

        out = pd.DataFrame(0.0, index=bars.index, columns=symbols)
        for sym in trade_symbols:
            out[sym] = raw[sym] * gate
        return out[bars.columns]

    def export_params(self) -> dict:
        return {
            "type": "tsmom_breadth_gate",
            "lookback": self._base.lookback,
            "skip": self._base.skip,
            "breadth_threshold": self.breadth_threshold,
            "trade_symbols": list(self.trade_symbols),
        }
