"""Time-series momentum, gated to a volatility-acceleration filter (see
brain/wiki/strategies/tsmom-vol-accel.md).

Hypothesis: [[tsmom-spy-qqq]]'s edge survives, and its worst blind spot
(fully invested through the entire 2020 COVID crash, since a 12-month
trailing return can't react within days) improves, if the raw signal is
gated off whenever short-window realized vol is expanding sharply versus
its own longer-window baseline -- a fast, self-referential, relative
check, structurally different from [[ms-shift-spy-vol-regime]]'s static
absolute-band gate on a different base signal.

Deliberately reuses tsmom_spy_qqq.Signal's `generate()` output unmodified
and multiplies it by a separately-computed, independently-causal gate --
same single-variable-follow-up discipline as v1->v2 and v1->v3: this
isolates the vol-acceleration question as one additive filter, not a
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


class Signal:
    def __init__(
        self,
        lookback: int = 252,
        skip: int = 21,
        vol_short_window: int = 5,
        vol_long_window: int = 63,
        vol_accel_threshold: float = 1.75,
    ) -> None:
        if vol_short_window < 2:
            raise ValueError("vol_short_window must be >= 2")
        if vol_long_window <= vol_short_window:
            raise ValueError("vol_long_window must be > vol_short_window")
        if vol_accel_threshold <= 1.0:
            raise ValueError("vol_accel_threshold must be > 1.0 (a no-op gate at <=1.0)")
        self._base = _tsmom.Signal(lookback, skip)
        self.vol_short_window = vol_short_window
        self.vol_long_window = vol_long_window
        self.vol_accel_threshold = vol_accel_threshold

    def generate(self, bars) -> pd.DataFrame:
        raw = self._base.generate(bars)
        out = {}
        for sym in bars.columns:
            close = bars.close[sym].to_numpy(dtype=float).tolist()
            gate = _vol_accel_gate(
                close, self.vol_short_window, self.vol_long_window, self.vol_accel_threshold
            )
            out[sym] = [w * g for w, g in zip(raw[sym].tolist(), gate)]
        return pd.DataFrame(out, index=bars.index)[bars.columns]

    def export_params(self) -> dict:
        return {
            "type": "tsmom_vol_accel",
            "lookback": self._base.lookback,
            "skip": self._base.skip,
            "vol_short_window": self.vol_short_window,
            "vol_long_window": self.vol_long_window,
            "vol_accel_threshold": self.vol_accel_threshold,
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


def _vol_accel_gate(
    close: list[float], short_window: int, long_window: int, threshold: float
) -> list[float]:
    """1.0 on days where short-window realized vol / long-window realized
    vol <= threshold; 0.0 once short-term vol has expanded past it. Both
    vols are computed from returns strictly before today, so this can
    never peek at today's own move, let alone the future."""
    n = len(close)
    returns = [0.0] * n
    for t in range(1, n):
        returns[t] = close[t] / close[t - 1] - 1.0

    gate = [0.0] * n
    for t in range(n):
        short_vol = _realized_vol(returns, t, short_window)
        long_vol = _realized_vol(returns, t, long_window)
        if short_vol is None or long_vol is None or long_vol == 0.0:
            continue
        ratio = short_vol / long_vol
        if ratio <= threshold:
            gate[t] = 1.0
    return gate
