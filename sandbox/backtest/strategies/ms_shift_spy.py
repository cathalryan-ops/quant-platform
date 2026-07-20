"""Market-Structure-Shift + Displacement (the first real strategy).

Hypothesis (see brain/wiki/strategies/ms-shift-spy.md): on daily charts, a
confirmed break of the most recent swing structure — a close beyond the last
confirmed swing high/low — that arrives with *displacement* (a wide-range
bar, range >= displacement_mult * ATR) precedes multi-day continuation.
Long-only in v1: a bullish shift goes long; a bearish shift flattens.

The logic is written as an explicit causal walk (day T uses only bars <= T)
so it passes the lookahead guard, and its arithmetic order matches the Rust
interpreter in engine-core exactly (golden-tested) — that is the ADR-0002
Python->Rust handoff for this family.

Swing detection is fractal: bar i is a swing high if its high strictly
exceeds every high in [i-k, i+k]; it is only *confirmed* (knowable) at bar
i+k, so at day T we confirm the swing centred on T-k using the window
[T-2k, T]. ATR is a simple mean of the last `atr_period` true ranges.
"""

from __future__ import annotations

import pandas as pd


class Signal:
    def __init__(
        self, swing_lookback: int = 3, atr_period: int = 14, displacement_mult: float = 1.5
    ) -> None:
        if swing_lookback < 1:
            raise ValueError("swing_lookback must be >= 1")
        if atr_period < 1:
            raise ValueError("atr_period must be >= 1")
        if displacement_mult <= 0:
            raise ValueError("displacement_mult must be > 0")
        self.swing_lookback = swing_lookback
        self.atr_period = atr_period
        self.displacement_mult = displacement_mult

    def generate(self, bars) -> pd.DataFrame:
        out = {}
        for sym in bars.columns:
            out[sym] = _weights(
                bars.high[sym].to_numpy(dtype=float).tolist(),
                bars.low[sym].to_numpy(dtype=float).tolist(),
                bars.close[sym].to_numpy(dtype=float).tolist(),
                self.swing_lookback,
                self.atr_period,
                self.displacement_mult,
            )
        return pd.DataFrame(out, index=bars.index)[bars.columns]

    def export_params(self) -> dict:
        """Fitted parameters for the Rust engines (ADR 0002 ruleset)."""
        return {
            "type": "ms_shift",
            "swing_lookback": self.swing_lookback,
            "atr_period": self.atr_period,
            "displacement_mult": self.displacement_mult,
        }


def _atr_at(high, low, close, t, period):
    """Simple mean of the last `period` true ranges ending at t, or None."""
    if t < period:
        return None
    total = 0.0
    for i in range(t - period + 1, t + 1):  # ascending — must match Rust order
        tr_hl = high[i] - low[i]
        tr_hc = abs(high[i] - close[i - 1])
        tr_lc = abs(low[i] - close[i - 1])
        total += max(tr_hl, tr_hc, tr_lc)
    return total / period


def _is_swing_high(high, i, k) -> bool:
    if i - k < 0 or i + k >= len(high):
        return False
    return all(high[i] > high[j] for j in range(i - k, i + k + 1) if j != i)


def _is_swing_low(low, i, k) -> bool:
    if i - k < 0 or i + k >= len(low):
        return False
    return all(low[i] < low[j] for j in range(i - k, i + k + 1) if j != i)


def _weights(high, low, close, k, period, mult):
    n = len(close)
    weights = [0.0] * n
    trend = 0.0
    last_swing_high = None
    last_swing_low = None
    for t in range(n):
        # 1. Confirm the swing centred on t-k (window [t-2k, t], all <= t).
        c = t - k
        if c >= 0:
            if _is_swing_high(high, c, k):
                last_swing_high = high[c]
            if _is_swing_low(low, c, k):
                last_swing_low = low[c]
        # 2. Evaluate a structure shift at t, gated on displacement.
        atr = _atr_at(high, low, close, t, period)
        if atr is not None and atr > 0.0:
            displaced = (high[t] - low[t]) >= mult * atr
            if displaced and last_swing_high is not None and close[t] > last_swing_high:
                trend = 1.0
            elif displaced and last_swing_low is not None and close[t] < last_swing_low:
                trend = 0.0
        weights[t] = trend
    return weights
