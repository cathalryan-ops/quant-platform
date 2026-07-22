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

2026-07-22: extended to cover short positions (negative weights) as well
as long, needed for the first long-short strategy in this vault
(pairs-trading/stat-arb). Previously any negative weight fell through to
the "else" branch unconditionally, silently forcing it flat regardless of
`stop_loss_pct` -- not a deliberate long-only design choice, just that no
strategy before this one ever produced a negative weight. The short side
is symmetric: entry price is the entry-day close, the stop check is a
`high` breach upward (mirroring the long side's `low` breach downward),
and both re-arm conditions mirror too (fresh same-direction 0->nonzero
transition, or cooldown-gated price reclaim -- `close` back AT OR BELOW
entry for a short, matching the long side's AT OR ABOVE). `high` is a new
keyword-only parameter defaulting to `None`; every existing call site and
unit test that never passes it is unaffected -- with `high=None`, a
negative weight still falls through to the old "force flat" behavior, so
long-only callers see byte-identical output. `backtest/engine.py` now
passes `bars.high` unconditionally, which is a no-op for every prior
strategy (none of them ever emit a negative weight) and only takes effect
for a strategy that actually shorts.

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
    high: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Force a position flat once price breaches its stop, per symbol.

    `shifted_weights` must already be in execution-timeline space (i.e.
    weights.shift(1) as used to build `target` today) — this operates on
    "what position is nominally held as of day t", not on the signal's raw
    decision day. Same-scale weights in, same-scale out; the caller still
    multiplies by max_position_pct afterward.

    Long side (positive weight):
    - Entry: the first day a symbol's weight is > 0 after being 0 (or after
      flipping from short). Entry price is that day's close (matches the
      engine's existing fill convention: `close` is the price series passed
      to `vbt.Portfolio.from_orders`).
    - Stop check starts the FOLLOWING day (you can't be stopped out on your
      own entry day — the entry fills at that day's close, after that
      day's low has already occurred). If a later day's low breaches
      `entry_price * (1 - stop_loss_pct/100)`, the position is forced flat
      from that day onward, and a `cooldown_sessions`-session countdown
      starts (see Re-arm below). `entry_price` is retained (not reset)
      after a stop, so a later price-reclaim check has something to
      compare against.

    Short side (negative weight) — mirrors the long side exactly, and only
    activates when `high` is supplied (see below): entry price is the
    entry-day close; the stop check is a `high` breach upward,
    `entry_price * (1 + stop_loss_pct/100)`, instead of the long side's
    `low` breach downward.

    `high` defaults to `None`. Every strategy in this vault before
    2026-07-22 is long-only, so no existing call site or unit test passes
    it. With `high=None`, a negative weight still falls straight through
    to "force flat" (the original, pre-2026-07-22 behavior) — this
    parameter is additive, not a behavior change, for any caller that
    doesn't pass it.

    Re-arm (Option C, combined): once stopped out, weight stays forced to
    0 until EITHER of the following fires, whichever comes first:
      (A) the raw signal produces a FRESH same-direction 0->nonzero
          transition — the original safety property, symmetric for
          shorts. Ungated by cooldown: this is already a rare event, so
          there's nothing to protect against here.
      (B) `cooldown_sessions` have elapsed since the stop AND that day's
          close reclaims the entry price — `>=` for a long (price
          recovering upward), `<=` for a short (price recovering
          downward). This bounds how long a slow-to-reverse signal can
          leave the position locked out through a recovery the raw signal
          itself would have ridden. `cooldown_sessions=0` (the default)
          means (B) is live starting the very next session.
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
        hi = high[sym].to_numpy(dtype=np.float64) if high is not None else None
        n = len(w)
        result = np.zeros(n)

        in_position = 0  # 0 = flat, 1 = long, -1 = short
        stopped = False
        stopped_direction = 0
        entry_price = 0.0
        prev_raw = 0.0
        cooldown_remaining = 0

        for t in range(n):
            raw = w[t]
            raw_sign = 1 if raw > 0.0 else (-1 if raw < 0.0 else 0)
            short_enabled = hi is not None

            if stopped:
                if cooldown_remaining > 0:
                    cooldown_remaining -= 1
                fresh_entry = (
                    prev_raw == 0.0 and raw_sign != 0 and raw_sign == stopped_direction
                )
                if stopped_direction == 1:
                    price_reclaimed = cooldown_remaining == 0 and c[t] >= entry_price
                else:
                    price_reclaimed = cooldown_remaining == 0 and c[t] <= entry_price
                if fresh_entry or price_reclaimed:
                    stopped = False  # (A) or (B) — whichever fired first

            can_hold = raw_sign == 1 or (raw_sign == -1 and short_enabled)

            if raw_sign != 0 and not stopped and can_hold:
                if in_position != raw_sign:
                    entry_price = c[t]
                    in_position = raw_sign
                    result[t] = raw  # entry day: no stop check possible yet
                else:
                    breached = (
                        lo[t] <= entry_price * (1.0 - stop_frac)
                        if raw_sign == 1
                        else hi[t] >= entry_price * (1.0 + stop_frac)
                    )
                    if breached:
                        result[t] = 0.0
                        in_position = 0
                        stopped = True
                        stopped_direction = raw_sign
                        cooldown_remaining = cooldown_sessions
                    else:
                        result[t] = raw
            else:
                in_position = 0
                result[t] = 0.0

            prev_raw = raw

        out[sym] = result

    return out
