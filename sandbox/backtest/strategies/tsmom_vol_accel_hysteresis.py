"""Time-series momentum, gated to a volatility-acceleration filter with
hysteresis (see brain/wiki/strategies/tsmom-vol-accel-hysteresis.md).

Hypothesis: [[tsmom-vol-accel]]'s gate correctly detects the COVID-crash
shock (flat time rose from 0% to ~47%) but more than doubles turnover
versus the ungated [[tsmom-spy-qqq]] baseline, and that extra whipsaw cost
is why aggregate Sharpe got worse rather than better. A single-threshold
gate chatters near its own boundary: on an ordinary week where the vol
ratio hovers around 1.75, it can cross back and forth repeatedly, closing
and reopening the position on noise rather than a real regime change.
Hysteresis (a lower re-entry threshold than the exit threshold) is the
standard fix for exactly this failure mode.

Deliberately keeps `vol_accel_exit_threshold=1.75` UNCHANGED from
tsmom-vol-accel (not re-fit) and adds exactly one new variable,
`vol_accel_reentry_threshold`, fixed below it -- same single-variable-
follow-up discipline as every prior step in this line.
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
        vol_short_window: int = 5,
        vol_long_window: int = 63,
        vol_accel_exit_threshold: float = 1.75,
        vol_accel_reentry_threshold: float = 1.25,
    ) -> None:
        if vol_short_window < 2:
            raise ValueError("vol_short_window must be >= 2")
        if vol_long_window <= vol_short_window:
            raise ValueError("vol_long_window must be > vol_short_window")
        if vol_accel_reentry_threshold <= 1.0:
            raise ValueError("vol_accel_reentry_threshold must be > 1.0")
        if vol_accel_exit_threshold <= vol_accel_reentry_threshold:
            raise ValueError("vol_accel_exit_threshold must be > vol_accel_reentry_threshold")
        self._base = _tsmom.Signal(lookback, skip)
        self.vol_short_window = vol_short_window
        self.vol_long_window = vol_long_window
        self.vol_accel_exit_threshold = vol_accel_exit_threshold
        self.vol_accel_reentry_threshold = vol_accel_reentry_threshold

    def generate(self, bars) -> pd.DataFrame:
        raw = self._base.generate(bars)
        out = {}
        for sym in bars.columns:
            close = bars.close[sym].to_numpy(dtype=float).tolist()
            gate = _vol_accel_hysteresis_gate(
                close,
                self.vol_short_window,
                self.vol_long_window,
                self.vol_accel_exit_threshold,
                self.vol_accel_reentry_threshold,
            )
            out[sym] = [w * g for w, g in zip(raw[sym].tolist(), gate)]
        return pd.DataFrame(out, index=bars.index)[bars.columns]

    def export_params(self) -> dict:
        return {
            "type": "tsmom_vol_accel_hysteresis",
            "lookback": self._base.lookback,
            "skip": self._base.skip,
            "vol_short_window": self.vol_short_window,
            "vol_long_window": self.vol_long_window,
            "vol_accel_exit_threshold": self.vol_accel_exit_threshold,
            "vol_accel_reentry_threshold": self.vol_accel_reentry_threshold,
        }


def _realized_vol(returns: list[float], t: int, window: int) -> float | None:
    """Population std of returns[t-window:t] -- strictly before t, never
    including today's own return. None if there isn't a full window yet."""
    if t < window:
        return None
    w = returns[t - window : t]
    mean = sum(w) / window
    var = sum((x - mean) ** 2 for x in w) / window
    return var**0.5


def _vol_accel_ratios(close: list[float], short_window: int, long_window: int) -> list[float | None]:
    """Short/long realized-vol ratio per session, or None where either
    window isn't full yet. Both vols are computed from returns strictly
    before today, so this can never peek at today's own move."""
    n = len(close)
    returns = [0.0] * n
    for t in range(1, n):
        returns[t] = close[t] / close[t - 1] - 1.0

    ratios: list[float | None] = [None] * n
    for t in range(n):
        short_vol = _realized_vol(returns, t, short_window)
        long_vol = _realized_vol(returns, t, long_window)
        if short_vol is None or long_vol is None or long_vol == 0.0:
            continue
        ratios[t] = short_vol / long_vol
    return ratios


def _hysteresis_from_ratios(
    ratios: list[float | None], exit_threshold: float, reentry_threshold: float
) -> list[float]:
    """1.0 while the gate is open, 0.0 while closed. Starts (and stays,
    wherever ratio is None -- warm-up or a zero-vol baseline) closed. Once
    open, closes when the ratio exceeds `exit_threshold`; once closed, only
    reopens once the ratio has dropped back under the lower
    `reentry_threshold` -- a single crossing back under `exit_threshold`
    alone is never enough to reopen it, unlike the single-threshold gate
    this replaces."""
    gate = [0.0] * len(ratios)
    open_ = False
    for t, ratio in enumerate(ratios):
        if ratio is not None:
            if open_:
                if ratio > exit_threshold:
                    open_ = False
            else:
                if ratio < reentry_threshold:
                    open_ = True
        gate[t] = 1.0 if open_ else 0.0
    return gate


def _vol_accel_hysteresis_gate(
    close: list[float],
    short_window: int,
    long_window: int,
    exit_threshold: float,
    reentry_threshold: float,
) -> list[float]:
    ratios = _vol_accel_ratios(close, short_window, long_window)
    return _hysteresis_from_ratios(ratios, exit_threshold, reentry_threshold)
