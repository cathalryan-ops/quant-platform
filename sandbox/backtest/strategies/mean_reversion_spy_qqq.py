"""Mean-reversion after an extreme single-day move (see
brain/wiki/strategies/mean-reversion-spy-qqq.md).

Hypothesis: an outsized single-day drop — a close-to-close return at least
`drop_mult` standard deviations below the trailing `lookback`-day mean —
is followed by short-horizon reversion often enough to clear costs. This
is the OPPOSITE premise to [[market-structure-shift]] (which buys
confirmed continuation, not a dip): no structure/swing/displacement logic
at all, just a volatility-scaled shock and a fixed holding period.

The logic is written as an explicit causal walk (day T uses only bars <=
T) so it passes the lookahead guard: the trigger threshold for day T is
estimated from the `lookback` days STRICTLY BEFORE T (today's own return
is compared against yesterday's estimate, never against a window that
includes itself), and the holding-period countdown is a pure function of
past trigger events.

Long-only, single position at a time: while `hold_days` is counting down,
a fresh drop does not re-trigger or extend the hold — this stays a clean,
falsifiable test of "does the reversion happen," not a pyramiding scheme.
"""

from __future__ import annotations

import pandas as pd


class Signal:
    def __init__(self, lookback: int = 20, drop_mult: float = 2.0, hold_days: int = 5) -> None:
        if lookback < 2:
            raise ValueError("lookback must be >= 2")
        if drop_mult <= 0:
            raise ValueError("drop_mult must be > 0")
        if hold_days < 1:
            raise ValueError("hold_days must be >= 1")
        self.lookback = lookback
        self.drop_mult = drop_mult
        self.hold_days = hold_days

    def generate(self, bars) -> pd.DataFrame:
        out = {}
        for sym in bars.columns:
            out[sym] = _weights(
                bars.close[sym].to_numpy(dtype=float).tolist(),
                self.lookback,
                self.drop_mult,
                self.hold_days,
            )
        return pd.DataFrame(out, index=bars.index)[bars.columns]

    def export_params(self) -> dict:
        """Fitted parameters — kept in the same shape as ms_shift's for
        ADR-0002 (Rust ruleset export), even though this strategy hasn't
        reached a stage that needs the Rust mirror yet."""
        return {
            "type": "mean_reversion",
            "lookback": self.lookback,
            "drop_mult": self.drop_mult,
            "hold_days": self.hold_days,
        }


def _rolling_std_excluding_today(returns: list[float], t: int, lookback: int) -> float | None:
    """Population std of returns[t-lookback : t] — the `lookback` days
    strictly before t, never including day t's own return. None if there
    isn't a full window of prior days yet."""
    if t < lookback:
        return None
    window = returns[t - lookback : t]
    mean = sum(window) / lookback
    var = sum((x - mean) ** 2 for x in window) / lookback
    return var**0.5


def _weights(close: list[float], lookback: int, drop_mult: float, hold_days: int) -> list[float]:
    n = len(close)
    weights = [0.0] * n
    returns = [0.0] * n
    for t in range(1, n):
        returns[t] = close[t] / close[t - 1] - 1.0

    hold_remaining = 0
    for t in range(n):
        if hold_remaining > 0:
            weights[t] = 1.0
            hold_remaining -= 1
            continue
        std = _rolling_std_excluding_today(returns, t, lookback)
        if std is not None and std > 0.0 and returns[t] <= -drop_mult * std:
            weights[t] = 1.0
            hold_remaining = hold_days - 1  # today is the 1st of hold_days sessions held
    return weights
