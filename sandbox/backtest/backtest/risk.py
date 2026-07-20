"""Risk overlays applied on top of a signal's raw weights, before portfolio
construction. Kept separate from signal.py/Signal.generate() deliberately:
the ADR-0002 Python<->Rust golden-test parity pins the signal's raw
trend decision, and risk controls are a distinct concern layered on top of
it, not part of it — see test_ms_shift_golden.py, which calls
Signal.generate() directly and never touches this module.

Today: a stop-loss overlay. Manifest-declared but previously unenforced —
found while investigating why ms-shift-spy-v1/v2 had mediocre-but-positive
folds (failed breakouts riding further than the strategy's own declared
risk tolerance before the signal itself reversed).

Follow-up (Option C, combined re-arm): plain enforcement turned out to make
walk-forward Sharpe *worse*, not better, on both v1 and v2. Root cause,
isolated on ms-shift-spy-v1/QQQ fold 2022-10 -> 2023-07: the raw signal's
own reversal is gated on a rare displaced structure break, so it can hold
one direction for many months at a time. Once stopped out mid-trend, the
original re-arm rule (fresh raw 0->>0 transition only) had no way back in
until that same rare reversal fired — missing the rest of the trend
entirely (QQQ: stopped 2022-12-05, didn't re-arm until 2023-10-06, ten
months later, after a +24% move). `stop_loss_cooldown_sessions` bounds
that lockout: after the cooldown elapses, a price reclaim of entry_price
re-arms too, whichever of the two conditions fires first.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def apply_stop_loss(
    shifted_weights: pd.DataFrame,
    close: pd.DataFrame,
    low: pd.DataFrame,
    stop_loss_pct: float,
    cooldown_sessions: int = 0,
) -> pd.DataFrame:
    """Force a long position flat once price breaches its stop, per symbol.

    `shifted_weights` must already be in execution-timeline space (i.e.
    weights.shift(1) as used to build `target` today) — this operates on
    "what position is nominally held as of day t", not on the signal's raw
    decision day. Long-only, 0/1-scale weights in, same scale out; the
    caller still multiplies by max_position_pct afterward.

    Semantics:
    - Entry: the first day a symbol's weight is > 0 after being 0. Entry
      price is that day's close (matches the engine's existing fill
      convention: `close` is the price series passed to
      `vbt.Portfolio.from_orders`).
    - Stop check starts the FOLLOWING day (you can't be stopped out on your
      own entry day — the entry fills at that day's close, after that
      day's low has already occurred). If a later day's low breaches
      `entry_price * (1 - stop_loss_pct/100)`, the position is forced flat
      from that day onward, and a `cooldown_sessions`-session countdown
      starts (see Re-arm below). `entry_price` is retained (not reset)
      after a stop, so a later price-reclaim check has something to
      compare against.
    - Re-arm (Option C, combined): once stopped out, weight stays forced to
      0 until EITHER of the following fires, whichever comes first:
        (A) the raw signal produces a FRESH 0->1 transition — the original
            safety property. Ungated by cooldown: this is already a rare
            event, so there's nothing to protect against here.
        (B) `cooldown_sessions` have elapsed since the stop AND that day's
            close reclaims (>=) `entry_price`. This bounds how long a
            slow-to-reverse trend-following signal (see module docstring)
            can leave the position locked out through a recovery the raw
            signal itself would have ridden. `cooldown_sessions=0` (the
            default) means (B) is live starting the very next session.
      Without gating (A), a stop that immediately re-triggers the same
      signal the next day isn't a real risk control — that property is
      preserved unchanged.
    """
    if stop_loss_pct <= 0:
        raise ValueError("stop_loss_pct must be > 0")
    if cooldown_sessions < 0:
        raise ValueError("cooldown_sessions must be >= 0")

    out = shifted_weights.copy().astype(np.float64)
    stop_frac = stop_loss_pct / 100.0

    for sym in shifted_weights.columns:
        w = shifted_weights[sym].to_numpy(dtype=np.float64)
        c = close[sym].to_numpy(dtype=np.float64)
        lo = low[sym].to_numpy(dtype=np.float64)
        n = len(w)
        result = np.zeros(n)

        in_position = False
        stopped = False
        entry_price = 0.0
        prev_raw = 0.0
        cooldown_remaining = 0

        for t in range(n):
            raw = w[t]

            if stopped:
                if cooldown_remaining > 0:
                    cooldown_remaining -= 1
                fresh_entry = prev_raw == 0.0 and raw > 0.0
                price_reclaimed = cooldown_remaining == 0 and c[t] >= entry_price
                if fresh_entry or price_reclaimed:
                    stopped = False  # (A) or (B) — whichever fired first

            if raw > 0.0 and not stopped:
                if not in_position:
                    entry_price = c[t]
                    in_position = True
                    result[t] = raw  # entry day: no stop check possible yet
                else:
                    if lo[t] <= entry_price * (1.0 - stop_frac):
                        result[t] = 0.0
                        in_position = False
                        stopped = True
                        cooldown_remaining = cooldown_sessions
                    else:
                        result[t] = raw
            else:
                in_position = False
                result[t] = 0.0

            prev_raw = raw

        out[sym] = result

    return out
