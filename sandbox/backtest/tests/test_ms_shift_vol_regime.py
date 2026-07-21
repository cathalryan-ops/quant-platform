"""Unit tests for the volatility-regime-gated ms_shift signal: the vol
gate itself, that it correctly zeroes out the base signal outside the
band, invalid params, and lookahead safety through the harness guard."""

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

from backtest.signal import BarFrame, generate_checked

_spec = importlib.util.spec_from_file_location(
    "ms_shift_vol_regime",
    Path(__file__).resolve().parents[1] / "strategies/ms_shift_vol_regime.py",
)
vr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vr)


def bars_from_ohlc(o, h, l, c) -> BarFrame:
    idx = pd.bdate_range("2020-01-01", periods=len(c))
    mk = lambda v: pd.DataFrame({"SPY": v}, index=idx)
    return BarFrame(open=mk(o), high=mk(h), low=mk(l), close=mk(c))


def test_vol_gate_zero_on_flat_prices():
    # Zero realized vol -> below vol_low -> gate never opens.
    close = [100.0] * 40
    gate = vr._vol_gate(close, window=20, vol_low=0.12, vol_high=0.35)
    assert all(g == 0.0 for g in gate)


def test_vol_gate_opens_in_band():
    rng = np.random.default_rng(5)
    # Calibrated to land in [0.12, 0.35] annualized: daily std ~0.014 ->
    # annualized ~0.014*sqrt(252) ~= 0.222.
    n = 60
    close = [100.0]
    for _ in range(n - 1):
        close.append(close[-1] * (1.0 + rng.normal(0, 0.014)))
    gate = vr._vol_gate(close, window=20, vol_low=0.12, vol_high=0.35)
    assert any(g == 1.0 for g in gate[20:]), "moderate daily vol should land inside the band"


def test_vol_gate_closes_above_band_in_a_crash():
    # 20 calm days, then an extreme-vol burst -> the day right after the
    # burst starts entering the window should push annualized vol > 0.35.
    close = [100.0] * 21
    rng = np.random.default_rng(1)
    for _ in range(20):
        close.append(close[-1] * (1.0 + rng.normal(0, 0.08)))  # violent daily swings
    gate = vr._vol_gate(close, window=20, vol_low=0.12, vol_high=0.35)
    assert gate[-1] == 0.0, "crisis-level trailing vol must close the gate"


def test_gate_zeroes_out_the_base_signal_outside_the_band():
    # Build the same displaced-bullish-break fixture used in
    # test_ms_shift.py's test_displacement_gates_entry (base signal fires
    # at index 7), but with essentially zero volatility throughout so the
    # vol gate stays closed the whole time.
    k, period, mult = 2, 3, 1.5
    high = [10.0, 11.0, 12.0, 11.0, 10.5, 10.7, 10.9, 20.0, 20.1]
    low = [9.5, 10.5, 11.5, 10.5, 10.0, 10.2, 10.4, 12.0, 19.9]
    close = [10.0, 10.8, 11.8, 10.8, 10.2, 10.5, 10.7, 19.0, 20.0]
    open_ = close
    bars = bars_from_ohlc(open_, high, low, close)
    sig = vr.Signal(
        swing_lookback=k, atr_period=period, displacement_mult=mult,
        vol_window=2, vol_low=0.90, vol_high=0.99,  # a band this data will never enter
    )
    out = sig.generate(bars)
    assert (out["SPY"] == 0.0).all(), "gate outside the band must zero out every session"


def test_invalid_params_raise():
    import pytest

    with pytest.raises(ValueError):
        vr.Signal(vol_window=1)
    with pytest.raises(ValueError):
        vr.Signal(vol_low=0.0)
    with pytest.raises(ValueError):
        vr.Signal(vol_low=0.3, vol_high=0.2)


def test_lookahead_safe_on_random_ohlc():
    rng = np.random.default_rng(31)
    n = 300
    close = 100 * np.exp(np.cumsum(rng.normal(0.0005, 0.012, n)))
    high = close * (1 + np.abs(rng.normal(0, 0.006, n)))
    low = close * (1 - np.abs(rng.normal(0, 0.006, n)))
    bars = bars_from_ohlc(close, high, low, close)
    sig = vr.Signal()
    out = generate_checked(sig, bars)  # raises LookaheadError on any leak
    assert set(np.unique(out.to_numpy())) <= {0.0, 1.0}


def test_export_params_roundtrips_shape():
    sig = vr.Signal(
        swing_lookback=3, atr_period=14, displacement_mult=1.5,
        vol_window=20, vol_low=0.12, vol_high=0.35,
    )
    assert sig.export_params() == {
        "type": "ms_shift_vol_regime",
        "swing_lookback": 3,
        "atr_period": 14,
        "displacement_mult": 1.5,
        "vol_window": 20,
        "vol_low": 0.12,
        "vol_high": 0.35,
    }
