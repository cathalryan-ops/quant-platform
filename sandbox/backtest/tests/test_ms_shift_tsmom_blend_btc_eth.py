"""Unit tests for the crypto-native ms-shift/tsmom blend: the blend
arithmetic itself, blend_weight edge cases (0.0 and 1.0 reduce to a pure
single-leg signal), invalid params, and lookahead safety through the
harness guard."""

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from backtest.signal import BarFrame, generate_checked

_spec = importlib.util.spec_from_file_location(
    "ms_shift_tsmom_blend_btc_eth",
    Path(__file__).resolve().parents[1] / "strategies/ms_shift_tsmom_blend_btc_eth.py",
)
blend_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(blend_mod)


def bars_from_ohlc(n: int, seed: int = 0) -> BarFrame:
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0.0004, 0.01, n)))
    high = close * (1.0 + np.abs(rng.normal(0, 0.004, n)))
    low = close * (1.0 - np.abs(rng.normal(0, 0.004, n)))
    idx = pd.bdate_range("2021-01-01", periods=n)
    mk = lambda arr: pd.DataFrame({"BTC/USD": arr}, index=idx)
    return BarFrame(open=mk(close), high=mk(high), low=mk(low), close=mk(close))


def test_default_blend_is_the_average_of_both_legs():
    bars = bars_from_ohlc(400, seed=1)
    sig = blend_mod.Signal(blend_weight=0.5)
    out = sig.generate(bars)
    a = sig._ms_shift.generate(bars)
    b = sig._tsmom.generate(bars)
    expected = 0.5 * a["BTC/USD"] + 0.5 * b["BTC/USD"]
    assert np.allclose(out["BTC/USD"].to_numpy(), expected.to_numpy())


def test_blend_weight_one_reduces_to_pure_ms_shift():
    bars = bars_from_ohlc(400, seed=2)
    sig = blend_mod.Signal(blend_weight=1.0)
    out = sig.generate(bars)
    a = sig._ms_shift.generate(bars)
    assert np.allclose(out["BTC/USD"].to_numpy(), a["BTC/USD"].to_numpy())


def test_blend_weight_zero_reduces_to_pure_tsmom():
    bars = bars_from_ohlc(400, seed=3)
    sig = blend_mod.Signal(blend_weight=0.0)
    out = sig.generate(bars)
    b = sig._tsmom.generate(bars)
    assert np.allclose(out["BTC/USD"].to_numpy(), b["BTC/USD"].to_numpy())


def test_output_bounded_in_zero_one():
    bars = bars_from_ohlc(400, seed=4)
    sig = blend_mod.Signal()
    out = generate_checked(sig, bars)
    assert ((out >= 0.0) & (out <= 1.0)).to_numpy().all()


def test_invalid_blend_weight_raises():
    with pytest.raises(ValueError):
        blend_mod.Signal(blend_weight=-0.01)
    with pytest.raises(ValueError):
        blend_mod.Signal(blend_weight=1.01)


def test_lookahead_safe_on_random_close():
    bars = bars_from_ohlc(400, seed=5)
    sig = blend_mod.Signal()
    generate_checked(sig, bars)  # raises LookaheadError on any leak


def test_export_params_roundtrips_shape():
    sig = blend_mod.Signal(
        swing_lookback=3,
        atr_period=14,
        displacement_mult=2.0,
        lookback=365,
        skip=30,
        blend_weight=0.5,
    )
    assert sig.export_params() == {
        "type": "ms_shift_tsmom_blend_btc_eth",
        "swing_lookback": 3,
        "atr_period": 14,
        "displacement_mult": 2.0,
        "lookback": 365,
        "skip": 30,
        "blend_weight": 0.5,
    }
