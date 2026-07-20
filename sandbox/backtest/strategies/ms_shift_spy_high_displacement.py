"""Market-Structure-Shift + Displacement — high-displacement variant (v2).

Single-variable follow-up to `ms_shift_spy.py` (see
brain/wiki/strategies/ms-shift-spy-high-displacement.md for the full
hypothesis). v1's real walk-forward result showed the edge concentrated in
3 of 12 folds (COVID crash+recovery, continued 2020-21 recovery, 2023-24 AI
rally) while the other 9 sat in a mediocre 0.0-0.82 Sharpe band. This
variant tests whether the mediocre folds are diluted by lower-conviction
entries: the ONLY change from v1 is `displacement_mult` default 1.5 -> 2.0
(swing_lookback and atr_period unchanged, isolating this one variable).
Logic is otherwise identical to v1 — see that file's docstring for the
mechanism and the lookahead/Rust-parity notes, which apply unchanged here.

Calibration note: synthetic i.i.d.-noise OHLC series were used to sanity
-check candidate multipliers before picking one (see
brain/wiki/strategies/ms-shift-spy-high-displacement.md). 3.0 fired zero
times over a synthetic 9-year-equivalent series; even 2.0 was sparse on
synthetic data. Real markets cluster volatility (autocorrelated true
range) far more than independent Gaussian draws, so synthetic firing
rates systematically UNDERESTIMATE real trade frequency — this is a
lower bound, not a prediction. 2.0 was chosen as a meaningful-but-not-
reckless step up from 1.5, to avoid the specific failure mode of an
empty-signal, statistically-meaningless result on real data.

`load_signal()` does not currently thread manifest-level params through to
the Signal constructor (see sandbox/backtest/backtest/signal.py's
`load_signal`), so a parameter variant needs its own entrypoint file rather
than a manifest field — same pattern as sma_cross.py vs ms_shift_spy.py
being independent, self-contained files.
"""

from __future__ import annotations

import pandas as pd


class Signal:
    def __init__(
        self, swing_lookback: int = 3, atr_period: int = 14, displacement_mult: float = 2.0
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
        c = t - k
        if c >= 0:
            if _is_swing_high(high, c, k):
                last_swing_high = high[c]
            if _is_swing_low(low, c, k):
                last_swing_low = low[c]
        atr = _atr_at(high, low, close, t, period)
        if atr is not None and atr > 0.0:
            displaced = (high[t] - low[t]) >= mult * atr
            if displaced and last_swing_high is not None and close[t] > last_swing_high:
                trend = 1.0
            elif displaced and last_swing_low is not None and close[t] < last_swing_low:
                trend = 0.0
        weights[t] = trend
    return weights
