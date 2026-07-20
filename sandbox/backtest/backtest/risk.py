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
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def apply_stop_loss(
    shifted_weights: pd.DataFrame,
    close: pd.DataFrame,
    low: pd.DataFrame,
    stop_loss_pct: float,
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
      from that day onward.
    - Re-arm: once stopped out, weight stays forced to 0 even if the raw
      signal is still nominally long, until the raw signal produces a
      FRESH 0->1 transition. Without this, a stop that immediately
      re-triggers the same signal the next day isn't a real risk control.
    """
    if stop_loss_pct <= 0:
        raise ValueError("stop_loss_pct must be > 0")

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

        for t in range(n):
            raw = w[t]
            if prev_raw == 0.0 and raw > 0.0:
                stopped = False  # fresh entry re-arms the stop

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
                    else:
                        result[t] = raw
            else:
                in_position = False
                result[t] = 0.0

            prev_raw = raw

        out[sym] = result

    return out
