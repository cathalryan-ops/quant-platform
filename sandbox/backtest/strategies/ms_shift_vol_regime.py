"""Market-structure-shift, gated to a volatility regime (see
brain/wiki/strategies/ms-shift-spy-vol-regime.md).

Hypothesis: [[ms-shift-spy]]'s edge is conditional on the prevailing
volatility regime, not (only) on displacement magnitude (already explored
by [[ms-shift-spy-high-displacement]], v2). Reuses v1's exact signal
unchanged (swing_lookback=3, atr_period=14, displacement_mult=1.5) and
adds one independent gate: trade only while trailing 20-day annualized
realized volatility falls within [vol_low, vol_high]. Below the band is
unusually calm — a "displaced" bar measured against a nearly-flat ATR is
more likely noise than a genuine structural break. Above the band is
crisis-level vol, where gap risk and discontinuous pricing undermine the
forced-exit mechanism the hypothesis relies on.

Deliberately reuses ms_shift_spy.Signal's `generate()` output unmodified
and multiplies it by a separately-computed, independently-causal gate —
this isolates the regime question as a single additive filter rather than
re-tuning any of v1's existing parameters (swing_lookback, atr_period,
displacement_mult are pinned to v1's values, not exposed for search here).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd

_ms_shift_spec = importlib.util.spec_from_file_location(
    "ms_shift_spy", Path(__file__).resolve().parent / "ms_shift_spy.py"
)
_ms_shift = importlib.util.module_from_spec(_ms_shift_spec)
_ms_shift_spec.loader.exec_module(_ms_shift)

TRADING_DAYS = 252


class Signal:
    def __init__(
        self,
        swing_lookback: int = 3,
        atr_period: int = 14,
        displacement_mult: float = 1.5,
        vol_window: int = 20,
        vol_low: float = 0.12,
        vol_high: float = 0.35,
    ) -> None:
        if vol_window < 2:
            raise ValueError("vol_window must be >= 2")
        if vol_low <= 0.0 or vol_high <= vol_low:
            raise ValueError("require 0 < vol_low < vol_high")
        self._base = _ms_shift.Signal(swing_lookback, atr_period, displacement_mult)
        self.vol_window = vol_window
        self.vol_low = vol_low
        self.vol_high = vol_high

    def generate(self, bars) -> pd.DataFrame:
        raw = self._base.generate(bars)
        out = {}
        for sym in bars.columns:
            close = bars.close[sym].to_numpy(dtype=float).tolist()
            gate = _vol_gate(close, self.vol_window, self.vol_low, self.vol_high)
            out[sym] = [w * g for w, g in zip(raw[sym].tolist(), gate)]
        return pd.DataFrame(out, index=bars.index)[bars.columns]

    def export_params(self) -> dict:
        return {
            "type": "ms_shift_vol_regime",
            "swing_lookback": self._base.swing_lookback,
            "atr_period": self._base.atr_period,
            "displacement_mult": self._base.displacement_mult,
            "vol_window": self.vol_window,
            "vol_low": self.vol_low,
            "vol_high": self.vol_high,
        }


def _vol_gate(close: list[float], window: int, vol_low: float, vol_high: float) -> list[float]:
    """1.0 on days where trailing annualized realized vol — computed from
    the `window` days STRICTLY BEFORE today, never including today's own
    return — falls within [vol_low, vol_high]; 0.0 otherwise."""
    n = len(close)
    returns = [0.0] * n
    for t in range(1, n):
        returns[t] = close[t] / close[t - 1] - 1.0

    gate = [0.0] * n
    for t in range(n):
        if t < window:
            continue
        window_returns = returns[t - window : t]
        mean = sum(window_returns) / window
        var = sum((x - mean) ** 2 for x in window_returns) / window
        vol_annualized = (var**0.5) * (TRADING_DAYS**0.5)
        if vol_low <= vol_annualized <= vol_high:
            gate[t] = 1.0
    return gate
