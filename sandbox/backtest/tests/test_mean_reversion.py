"""Unit tests for the mean-reversion signal: trigger detection, fixed
holding period, no re-trigger while held, and — critically — lookahead
safety through the harness guard."""

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

from backtest.signal import BarFrame, generate_checked

_spec = importlib.util.spec_from_file_location(
    "mean_reversion_spy_qqq",
    Path(__file__).resolve().parents[1] / "strategies/mean_reversion_spy_qqq.py",
)
mr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mr)


def bars_from_close(c) -> BarFrame:
    idx = pd.bdate_range("2020-01-01", periods=len(c))
    mk = lambda v: pd.DataFrame({"SPY": v}, index=idx)
    return BarFrame(open=mk(c), high=mk(c), low=mk(c), close=mk(c))


def test_no_trigger_on_flat_prices():
    close = [100.0] * 30
    w = mr._weights(close, lookback=10, drop_mult=2.0, hold_days=5)
    assert all(x == 0.0 for x in w), "zero volatility, zero return -> never triggers"


def test_extreme_drop_triggers_and_holds_for_fixed_period():
    # 15 flat days to build a stable (zero) vol estimate, then one sharp
    # drop, then flat again. std of an all-zero-return window is exactly
    # 0.0, so ANY nonzero drop with a positive drop_mult would divide by
    # zero if not guarded -- use a tiny bit of noise instead so std > 0.
    close = [100.0]
    for i in range(1, 15):
        close.append(close[-1] * (1.0 + (0.001 if i % 2 == 0 else -0.001)))
    trigger_day_price = close[-1] * (1.0 - 0.10)  # a 10% single-day drop
    close.append(trigger_day_price)
    for _ in range(10):
        close.append(close[-1])  # flat afterward, nothing to trigger again

    w = mr._weights(close, lookback=10, drop_mult=2.0, hold_days=5)
    trigger_idx = 15
    assert w[trigger_idx] == 1.0, "the 10% drop must trigger entry on its own day"
    assert w[trigger_idx - 1] == 0.0, "nothing before the drop should be long"
    assert w[trigger_idx : trigger_idx + 5] == [1.0] * 5, "held for exactly hold_days sessions"
    assert w[trigger_idx + 5] == 0.0, "flat again once the hold period ends"


def test_no_retrigger_while_holding():
    # Two drops close together: the second must NOT restart/extend the hold.
    close = [100.0]
    for i in range(1, 15):
        close.append(close[-1] * (1.0 + (0.001 if i % 2 == 0 else -0.001)))
    close.append(close[-1] * 0.90)  # drop 1 (index 15)
    close.append(close[-1] * 0.90)  # drop 2, one day later (index 16), still within the hold
    for _ in range(10):
        close.append(close[-1])  # flat afterward, long enough to observe the full hold window

    w = mr._weights(close, lookback=10, drop_mult=2.0, hold_days=5)
    # Regardless of whether day 16 "would" trigger on its own, hold_remaining
    # from day 15 must simply count down -- exactly 5 sessions long from the
    # first trigger, not extended by the second drop.
    assert w[15:20] == [1.0] * 5
    assert w[20] == 0.0


def test_invalid_params_raise():
    import pytest

    with pytest.raises(ValueError):
        mr.Signal(lookback=1)
    with pytest.raises(ValueError):
        mr.Signal(drop_mult=0.0)
    with pytest.raises(ValueError):
        mr.Signal(hold_days=0)


def test_lookahead_safe_on_random_ohlc():
    rng = np.random.default_rng(23)
    n = 300
    close = 100 * np.exp(np.cumsum(rng.normal(0.0003, 0.015, n)))
    bars = bars_from_close(close)
    sig = mr.Signal(lookback=20, drop_mult=2.0, hold_days=5)
    out = generate_checked(sig, bars)  # raises LookaheadError on any leak
    assert set(np.unique(out.to_numpy())) <= {0.0, 1.0}


def test_export_params_roundtrips_shape():
    sig = mr.Signal(lookback=15, drop_mult=1.75, hold_days=3)
    assert sig.export_params() == {
        "type": "mean_reversion",
        "lookback": 15,
        "drop_mult": 1.75,
        "hold_days": 3,
    }
