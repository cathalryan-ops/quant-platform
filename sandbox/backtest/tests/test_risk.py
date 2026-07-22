"""Offline, deterministic tests for the stop-loss overlay (backtest/risk.py).
No live data or network access needed."""

import pandas as pd
import pytest

from backtest.risk import apply_stop_loss


def frame(values: list[float]) -> pd.DataFrame:
    return pd.DataFrame({"SPY": values})


def test_no_stop_hit_passes_weights_through_unchanged():
    weights = frame([0.0, 1.0, 1.0, 1.0, 0.0])
    close = frame([100.0, 101.0, 102.0, 103.0, 103.0])
    low = frame([99.0, 100.5, 101.5, 102.5, 102.0])  # never breaches a 2% stop
    out = apply_stop_loss(weights, close, low, stop_loss_pct=2.0)
    assert out["SPY"].tolist() == [0.0, 1.0, 1.0, 1.0, 0.0]


def test_stop_triggers_and_forces_flat():
    # Entry at day 1 (close=100). Day 2's low (97) breaches 100*(1-0.02)=98.
    weights = frame([0.0, 1.0, 1.0, 1.0, 1.0])
    close = frame([99.0, 100.0, 96.0, 95.0, 94.0])
    low = frame([98.0, 99.5, 97.0, 94.0, 93.0])
    out = apply_stop_loss(weights, close, low, stop_loss_pct=2.0)
    assert out["SPY"].tolist() == [0.0, 1.0, 0.0, 0.0, 0.0]


def test_entry_day_itself_is_never_stopped_out():
    # Entry day's own low (way below its own close) must not trigger a stop
    # — the stop check starts the day AFTER entry, matching the close-fill
    # convention (you can't be stopped out before you've filled).
    weights = frame([0.0, 1.0, 0.0])
    close = frame([100.0, 100.0, 100.0])
    low = frame([100.0, 50.0, 100.0])  # entry day's low is deeply below entry price
    out = apply_stop_loss(weights, close, low, stop_loss_pct=2.0)
    assert out["SPY"].tolist() == [0.0, 1.0, 0.0]


def test_stopped_position_does_not_reenter_until_fresh_signal():
    # Stopped out on day 2; raw signal stays 1 through day 4 — must stay
    # flat until the raw signal drops to 0 and rises again (day 6).
    weights = frame([0.0, 1.0, 1.0, 1.0, 1.0, 0.0, 1.0])
    close = frame([100.0, 100.0, 96.0, 96.0, 96.0, 96.0, 96.0])
    low = frame([99.0, 99.0, 97.0, 99.0, 99.0, 95.0, 95.5])
    out = apply_stop_loss(weights, close, low, stop_loss_pct=2.0)
    # index: 0     1     2     3     4     5     6
    assert out["SPY"].tolist() == [0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0]


def test_symbols_are_independent():
    weights = frame([0.0, 1.0, 1.0])
    weights["QQQ"] = [0.0, 1.0, 1.0]
    close = frame([100.0, 100.0, 100.0])
    close["QQQ"] = [200.0, 200.0, 200.0]
    low = frame([99.0, 99.0, 90.0])  # SPY: stops out on day 2
    low["QQQ"] = [199.0, 199.0, 199.0]  # QQQ: never stops
    out = apply_stop_loss(weights, close, low, stop_loss_pct=2.0)
    assert out["SPY"].tolist() == [0.0, 1.0, 0.0]
    assert out["QQQ"].tolist() == [0.0, 1.0, 1.0]


def test_invalid_stop_loss_pct_raises():
    weights = frame([0.0, 1.0])
    close = frame([100.0, 100.0])
    low = frame([99.0, 99.0])
    with pytest.raises(ValueError):
        apply_stop_loss(weights, close, low, stop_loss_pct=0.0)
    with pytest.raises(ValueError):
        apply_stop_loss(weights, close, low, stop_loss_pct=-1.0)


def test_invalid_cooldown_sessions_raises():
    weights = frame([0.0, 1.0])
    close = frame([100.0, 100.0])
    low = frame([99.0, 99.0])
    with pytest.raises(ValueError):
        apply_stop_loss(weights, close, low, stop_loss_pct=2.0, cooldown_sessions=-1)


# --- Option C: combined re-arm (fresh raw transition OR post-cooldown price
# reclaim, whichever fires first) — see risk.py module docstring for the
# ms-shift-spy-v1/QQQ fold that motivated this. ---


def test_price_reclaim_rearms_even_though_raw_signal_never_drops_to_zero():
    # Raw signal goes long at day 1 and STAYS long the whole series (the
    # slow-regime case) — the original re-arm rule would never fire again.
    weights = frame([0.0, 1.0, 1.0, 1.0, 1.0, 1.0])
    close = frame([100.0, 100.0, 90.0, 85.0, 90.0, 101.0])
    low = frame([99.0, 99.0, 88.0, 84.0, 89.0, 100.0])
    out = apply_stop_loss(weights, close, low, stop_loss_pct=2.0, cooldown_sessions=1)
    # index:                0     1     2     3     4     5
    assert out["SPY"].tolist() == [0.0, 1.0, 0.0, 0.0, 0.0, 1.0]


def test_price_reclaim_is_gated_by_cooldown():
    # Price reclaims entry_price as early as day 3, but cooldown_sessions=3
    # must suppress re-arm until day 5 regardless.
    weights = frame([0.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0])
    close = frame([100.0, 100.0, 90.0, 101.0, 101.0, 101.0, 101.0])
    low = frame([99.0, 99.0, 88.0, 100.0, 100.0, 100.0, 100.0])
    out = apply_stop_loss(weights, close, low, stop_loss_pct=2.0, cooldown_sessions=3)
    # index:                0     1     2     3     4     5     6
    assert out["SPY"].tolist() == [0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 1.0]


def test_fresh_transition_rearm_ignores_cooldown():
    # A fresh raw 0->1 transition must re-arm immediately even while a long
    # cooldown is still counting down — condition (A) is never gated.
    weights = frame([0.0, 1.0, 1.0, 0.0, 1.0])
    close = frame([100.0, 100.0, 90.0, 90.0, 90.0])
    low = frame([99.0, 99.0, 88.0, 89.0, 89.0])
    out = apply_stop_loss(weights, close, low, stop_loss_pct=2.0, cooldown_sessions=10)
    # index:                0     1     2     3     4
    assert out["SPY"].tolist() == [0.0, 1.0, 0.0, 0.0, 1.0]


def test_cooldown_zero_default_matches_original_next_session_reentry_behavior():
    # cooldown_sessions defaults to 0 — must reproduce the pre-Option-C
    # fixture exactly when the raw signal itself provides the re-entry.
    weights = frame([0.0, 1.0, 1.0, 1.0, 1.0, 0.0, 1.0])
    close = frame([100.0, 100.0, 96.0, 96.0, 96.0, 96.0, 96.0])
    low = frame([99.0, 99.0, 97.0, 99.0, 99.0, 95.0, 95.5])
    out = apply_stop_loss(weights, close, low, stop_loss_pct=2.0)
    assert out["SPY"].tolist() == [0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0]


# --- 2026-07-22: short-side support (needed for pairs-trading/stat-arb,
# the first long-short strategy in this vault) — see risk.py module
# docstring. `high` defaults to None, so every test above (none of which
# pass it) continues to exercise the original long-only-with-shorts-zeroed
# behavior unchanged. ---


def test_negative_weight_without_high_falls_through_to_flat_unchanged():
    # No `high` supplied (the default) -- a short-side weight must still be
    # forced flat exactly like before 2026-07-22, not silently traded.
    weights = frame([0.0, -1.0, -1.0])
    close = frame([100.0, 100.0, 100.0])
    low = frame([99.0, 99.0, 99.0])
    out = apply_stop_loss(weights, close, low, stop_loss_pct=2.0)
    assert out["SPY"].tolist() == [0.0, 0.0, 0.0]


def test_short_position_passes_through_when_not_stopped():
    weights = frame([0.0, -1.0, -1.0, -1.0])
    close = frame([100.0, 100.0, 99.0, 98.0])
    low = frame([99.0, 99.0, 98.0, 97.0])
    high = frame([101.0, 100.5, 100.0, 99.0])  # never breaches a 2% stop (>=102)
    out = apply_stop_loss(weights, close, low, stop_loss_pct=2.0, high=high)
    assert out["SPY"].tolist() == [0.0, -1.0, -1.0, -1.0]


def test_short_stop_triggers_on_high_breach_and_forces_flat():
    # Entry at day 1 (close=100), short stop at 100*(1+0.02)=102.
    # Day 2's high (103) breaches it.
    weights = frame([0.0, -1.0, -1.0, -1.0, -1.0])
    close = frame([99.0, 100.0, 104.0, 105.0, 106.0])
    low = frame([98.0, 99.5, 100.0, 104.0, 105.0])
    high = frame([100.0, 100.5, 103.0, 106.0, 107.0])
    out = apply_stop_loss(weights, close, low, stop_loss_pct=2.0, high=high)
    assert out["SPY"].tolist() == [0.0, -1.0, 0.0, 0.0, 0.0]


def test_short_entry_day_itself_is_never_stopped_out():
    weights = frame([0.0, -1.0, 0.0])
    close = frame([100.0, 100.0, 100.0])
    high = frame([100.0, 150.0, 100.0])  # entry day's own high is deeply above entry
    low = frame([100.0, 100.0, 100.0])
    out = apply_stop_loss(weights, close, low, stop_loss_pct=2.0, high=high)
    assert out["SPY"].tolist() == [0.0, -1.0, 0.0]


def test_short_price_reclaim_rearms_after_cooldown():
    # Stopped out day 2 (high breach); cooldown=1, and close reclaims
    # (drops back to/below) entry_price=100 on day 4.
    weights = frame([0.0, -1.0, -1.0, -1.0, -1.0])
    close = frame([100.0, 100.0, 103.0, 103.0, 100.0])
    low = frame([99.0, 99.0, 102.0, 102.0, 99.0])
    high = frame([100.0, 100.5, 103.0, 103.0, 100.5])
    out = apply_stop_loss(weights, close, low, stop_loss_pct=2.0, cooldown_sessions=1, high=high)
    # index:                0     1      2    3     4
    assert out["SPY"].tolist() == [0.0, -1.0, 0.0, 0.0, -1.0]


def test_long_and_short_are_independent_directions_on_the_same_symbol():
    # A direct sign flip (long -> short) without passing through 0 is
    # treated as a fresh entry in the new direction, not a stop.
    weights = frame([0.0, 1.0, -1.0, -1.0])
    close = frame([100.0, 100.0, 100.0, 100.0])
    low = frame([99.0, 99.0, 99.0, 99.0])
    high = frame([101.0, 101.0, 101.0, 101.0])
    out = apply_stop_loss(weights, close, low, stop_loss_pct=2.0, high=high)
    assert out["SPY"].tolist() == [0.0, 1.0, -1.0, -1.0]
