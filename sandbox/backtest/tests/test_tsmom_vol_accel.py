"""Unit tests for the vol-acceleration-gated tsmom signal: the gate
itself, that it correctly zeroes out the base signal once short-term vol
outruns its baseline, invalid params, and lookahead safety through the
harness guard."""

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from backtest.signal import BarFrame, generate_checked

_spec = importlib.util.spec_from_file_location(
    "tsmom_vol_accel",
    Path(__file__).resolve().parents[1] / "strategies/tsmom_vol_accel.py",
)
va = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(va)


def bars_from_close(close: list[float]) -> BarFrame:
    idx = pd.bdate_range("2016-01-01", periods=len(close))
    mk = lambda v: pd.DataFrame({"SPY": v}, index=idx)
    return BarFrame(open=mk(close), high=mk(close), low=mk(close), close=mk(close))


def test_gate_open_on_flat_prices():
    # Zero vol everywhere -> ratio is 0/0 -> undefined -> stays closed
    # (never divides by zero, never fires on a degenerate ratio).
    close = [100.0] * 80
    gate = va._vol_accel_gate(close, short_window=5, long_window=63, threshold=1.75)
    assert all(g == 0.0 for g in gate)


def test_gate_open_on_steady_moderate_vol():
    rng = np.random.default_rng(7)
    close = [100.0]
    for _ in range(99):
        close.append(close[-1] * (1.0 + rng.normal(0, 0.01)))
    gate = va._vol_accel_gate(close, short_window=5, long_window=63, threshold=1.75)
    # Steady-state vol: short-window and long-window vol estimates should
    # mostly agree, ratio should mostly stay under a 1.75x threshold.
    assert sum(gate[63:]) / len(gate[63:]) > 0.5


def test_gate_closes_on_a_sudden_vol_spike():
    rng = np.random.default_rng(3)
    close = [100.0]
    for _ in range(80):
        close.append(close[-1] * (1.0 + rng.normal(0, 0.006)))  # calm baseline
    for _ in range(5):
        close.append(close[-1] * (1.0 + rng.normal(0, 0.06)))  # violent burst
    gate = va._vol_accel_gate(close, short_window=5, long_window=63, threshold=1.75)
    assert gate[-1] == 0.0, "a sharp short-term vol expansion must close the gate"


def test_gate_zeroes_out_the_base_signal_when_closed():
    # Strong sustained uptrend (base tsmom signal fires long by day 273),
    # then an abrupt violent burst right at the end -- the vol-accel gate
    # should zero the position out even though the base trend signal is
    # still unambiguously long.
    close = [100.0]
    for _ in range(299):
        close.append(close[-1] * (1.0 + 0.001))
    # A violent burst: large alternating-sign swings, so short-window
    # *dispersion* (not just drift) spikes -- realized vol is a variance
    # measure, and a constant-magnitude one-directional move wouldn't
    # actually raise it.
    for swing in (0.10, -0.12, 0.09, -0.11, 0.08):
        close.append(close[-1] * (1.0 + swing))
    bars = bars_from_close(close)
    sig = va.Signal(lookback=252, skip=21, vol_short_window=5, vol_long_window=63, vol_accel_threshold=1.75)
    out = sig.generate(bars)
    base = sig._base.generate(bars)
    assert base["SPY"].iloc[-1] == 1.0, "base trend signal is still long"
    assert out["SPY"].iloc[-1] == 0.0, "vol-accel gate must override it to flat"


def test_invalid_params_raise():
    with pytest.raises(ValueError):
        va.Signal(vol_short_window=1)
    with pytest.raises(ValueError):
        va.Signal(vol_short_window=10, vol_long_window=10)
    with pytest.raises(ValueError):
        va.Signal(vol_accel_threshold=1.0)


def test_lookahead_safe_on_random_close():
    rng = np.random.default_rng(11)
    n = 400
    close = 100 * np.exp(np.cumsum(rng.normal(0.0003, 0.012, n)))
    bars = bars_from_close(list(close))
    sig = va.Signal()
    out = generate_checked(sig, bars)  # raises LookaheadError on any leak
    assert set(np.unique(out.to_numpy())) <= {0.0, 1.0}


def test_export_params_roundtrips_shape():
    sig = va.Signal(
        lookback=252, skip=21, vol_short_window=5, vol_long_window=63, vol_accel_threshold=1.75
    )
    assert sig.export_params() == {
        "type": "tsmom_vol_accel",
        "lookback": 252,
        "skip": 21,
        "vol_short_window": 5,
        "vol_long_window": 63,
        "vol_accel_threshold": 1.75,
    }
