"""Unit tests for the market-structure-shift + displacement signal:
swing detection, displacement gating, long-only behaviour, and — critically —
lookahead safety through the harness guard."""

import numpy as np
import pandas as pd

from backtest.signal import BarFrame, generate_checked

import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "ms_shift_spy", Path(__file__).resolve().parents[1] / "strategies/ms_shift_spy.py"
)
ms = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ms)


def bars_from_ohlc(o, h, l, c) -> BarFrame:
    idx = pd.bdate_range("2020-01-01", periods=len(c))
    mk = lambda v: pd.DataFrame({"SPY": v}, index=idx)
    return BarFrame(open=mk(o), high=mk(h), low=mk(l), close=mk(c))


def test_swing_high_and_low_detection():
    high = [1, 2, 3, 2, 1]
    low = [1, 0, -1, 0, 1]
    assert ms._is_swing_high(high, 2, 2)  # centre is the peak
    assert not ms._is_swing_high(high, 1, 2)
    assert ms._is_swing_low(low, 2, 2)  # centre is the trough
    # Unconfirmable near the edges (not enough neighbours):
    assert not ms._is_swing_high(high, 0, 2)
    assert not ms._is_swing_high(high, 4, 2)


def test_displacement_gates_entry():
    # Build a clean bullish break: a swing high forms, then price closes above
    # it on a wide-range (displaced) bar → long. A later narrow break would
    # NOT flip (displacement gate).
    k, period, mult = 2, 3, 1.5
    # indices:      0    1    2    3    4    5    6    7    8
    high = [10.0, 11.0, 12.0, 11.0, 10.5, 10.7, 10.9, 20.0, 20.1]
    low = [9.5, 10.5, 11.5, 10.5, 10.0, 10.2, 10.4, 12.0, 19.9]
    close = [10.0, 10.8, 11.8, 10.8, 10.2, 10.5, 10.7, 19.0, 20.0]
    open_ = close
    w = ms._weights(high, low, close, k, period, mult)
    # Swing high is index 2 (high 12), confirmed at index 4. The displaced
    # breakout bar is index 7 (range 8.0 >> ATR), closing at 19 > 12 → long.
    assert w[7] == 1.0
    assert w[:7] == [0.0] * 7  # nothing fires before the displaced break
    assert w[8] == 1.0  # holds long


def test_no_displacement_no_entry():
    # Same structure but the breakout bar is narrow (no displacement) → flat.
    k, period, mult = 2, 3, 5.0  # demanding displacement multiple
    high = [10.0, 11.0, 12.0, 11.0, 10.5, 10.7, 10.9, 12.5, 12.6]
    low = [9.5, 10.5, 11.5, 10.5, 10.0, 10.2, 10.4, 12.3, 12.4]
    close = [10.0, 10.8, 11.8, 10.8, 10.2, 10.5, 10.7, 12.4, 12.5]
    w = ms._weights(high, low, close, k, period, mult)
    assert all(x == 0.0 for x in w), "narrow break must not trigger a long"


def test_lookahead_safe_on_random_ohlc():
    rng = np.random.default_rng(11)
    n = 260
    close = 100 * np.exp(np.cumsum(rng.normal(0.0005, 0.012, n)))
    high = close * (1 + np.abs(rng.normal(0, 0.006, n)))
    low = close * (1 - np.abs(rng.normal(0, 0.006, n)))
    bars = bars_from_ohlc(close, high, low, close)
    sig = ms.Signal(swing_lookback=3, atr_period=14, displacement_mult=1.5)
    # Raises LookaheadError if any past output changes under truncation.
    out = generate_checked(sig, bars)
    assert set(np.unique(out.to_numpy())) <= {0.0, 1.0}


def test_export_params_roundtrips_shape():
    sig = ms.Signal(swing_lookback=2, atr_period=10, displacement_mult=2.0)
    assert sig.export_params() == {
        "type": "ms_shift",
        "swing_lookback": 2,
        "atr_period": 10,
        "displacement_mult": 2.0,
    }
