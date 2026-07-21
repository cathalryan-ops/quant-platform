"""Time-series momentum with continuous volatility-targeted position
sizing (see brain/wiki/strategies/tsmom-vol-target.md).

Hypothesis: [[tsmom-vol-accel]] and [[tsmom-vol-accel-hysteresis]] both
tried to fix tsmom's blind spot to fast shocks with a BINARY long/flat
gate, and both found most of the resulting cost was the discrete
round-trip cost of gate crossings, not a flaw in the underlying idea that
de-risking during high vol helps (tsmom-vol-accel-hysteresis: turnover
still 2x the ungated baseline even with hysteresis). This tests the
structurally different alternative flagged in that page's retirement:
instead of an on/off gate, continuously SCALE the position size down as
realized volatility rises above a fixed annualized target -- a smooth
function of vol with no threshold to chatter across. Capped at the base
signal's own weight (never levers up when vol is unusually calm), since
the platform's Signal protocol is long-only, no-leverage in v1.

Deliberately reuses tsmom_spy_qqq.Signal's `generate()` output unmodified
and multiplies it by a separately-computed, independently-causal scalar --
same single-variable-follow-up discipline as the rest of this line: this
isolates the vol-targeting question as one additive scaling factor, not a
re-tuning of tsmom's lookback/skip (pinned to its existing values, not
exposed for search here).
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

TRADING_DAYS = 252


class Signal:
    def __init__(
        self,
        lookback: int = 252,
        skip: int = 21,
        vol_window: int = 20,
        vol_target: float = 0.15,
    ) -> None:
        if vol_window < 2:
            raise ValueError("vol_window must be >= 2")
        if vol_target <= 0.0:
            raise ValueError("vol_target must be > 0")
        self._base = _tsmom.Signal(lookback, skip)
        self.vol_window = vol_window
        self.vol_target = vol_target

    def generate(self, bars) -> pd.DataFrame:
        raw = self._base.generate(bars)
        out = {}
        for sym in bars.columns:
            close = bars.close[sym].to_numpy(dtype=float).tolist()
            scalar = _vol_target_scalar(close, self.vol_window, self.vol_target)
            out[sym] = [w * s for w, s in zip(raw[sym].tolist(), scalar)]
        return pd.DataFrame(out, index=bars.index)[bars.columns]

    def export_params(self) -> dict:
        return {
            "type": "tsmom_vol_target",
            "lookback": self._base.lookback,
            "skip": self._base.skip,
            "vol_window": self.vol_window,
            "vol_target": self.vol_target,
        }


def _realized_vol_annualized(returns: list[float], t: int, window: int) -> float | None:
    """Annualized population std of returns[t-window:t] -- strictly before
    t, never including today's own return. None if there isn't a full
    window yet."""
    if t < window:
        return None
    w = returns[t - window : t]
    mean = sum(w) / window
    var = sum((x - mean) ** 2 for x in w) / window
    return (var**0.5) * (TRADING_DAYS**0.5)


def _vol_target_scalar(close: list[float], window: int, vol_target: float) -> list[float]:
    """min(1.0, vol_target / trailing annualized realized vol) -- a smooth,
    continuous de-risking factor with no threshold to cross, unlike a
    binary gate. 0.0 wherever realized vol isn't yet estimable (warm-up)
    or is exactly zero, consistent with every other gate/signal in this
    vault defaulting to flat rather than dividing by zero."""
    n = len(close)
    returns = [0.0] * n
    for t in range(1, n):
        returns[t] = close[t] / close[t - 1] - 1.0

    scalar = [0.0] * n
    for t in range(n):
        vol = _realized_vol_annualized(returns, t, window)
        if vol is None or vol <= 0.0:
            continue
        scalar[t] = min(1.0, vol_target / vol)
    return scalar
