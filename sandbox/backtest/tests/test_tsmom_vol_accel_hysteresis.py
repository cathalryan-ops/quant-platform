"""Unit tests for the hysteresis-gated tsmom signal: starts closed, opens
only below the re-entry threshold, closes only above the exit threshold,
resists chatter right at the exit boundary, invalid params, and
lookahead safety through the harness guard."""

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from backtest.signal import BarFrame, generate_checked

_spec = importlib.util.spec_from_file_location(
    "tsmom_vol_accel_hysteresis",
    Path(__file__).resolve().parents[1] / "strategies/tsmom_vol_accel_hysteresis.py",
)
vah = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vah)


def bars_from_close(close: list[float]) -> BarFrame:
    idx = pd.bdate_range("2016-01-01", periods=len(close))
    mk = lambda v: pd.DataFrame({"SPY": v}, index=idx)
    return BarFrame(open=mk(close), high=mk(close), low=mk(close), close=mk(close))


def test_gate_starts_closed_during_warmup():
    close = [100.0] * 80
    gate = vah._vol_accel_hysteresis_gate(
        close, short_window=5, long_window=63, exit_threshold=1.75, reentry_threshold=1.25
    )
    assert all(g == 0.0 for g in gate[:63])


def test_a_single_threshold_gate_chatters_where_hysteresis_does_not():
    # A hand-constructed ratio path that dips to exactly the exit threshold
    # (1.75) and back up repeatedly, staying in the 1.25-1.75 "dead zone"
    # the whole time -- noisy, but never a real regime change back to calm.
    # A single-threshold gate (tsmom_vol_accel.py's convention: open iff
    # ratio <= threshold) would flip open every time the path touches 1.75
    # or below; hysteresis must stay closed throughout, since the ratio
    # never drops under the lower 1.25 re-entry bar.
    ratios: list[float | None] = [2.0, 2.0]  # clearly closes both gates
    dead_zone = [1.75, 1.5, 1.75, 1.3, 1.75, 1.4, 1.75, 1.6]
    ratios += dead_zone

    single_open = [r is not None and r <= 1.75 for r in ratios]
    hyst_gate = vah._hysteresis_from_ratios(ratios, exit_threshold=1.75, reentry_threshold=1.25)

    assert any(single_open[2:]), "single-threshold gate reopens somewhere in the dead zone"
    assert all(g == 0.0 for g in hyst_gate[2:]), "hysteresis gate must stay closed throughout the dead zone"


def test_gate_reopens_once_ratio_drops_below_reentry():
    close = [100.0]
    rng = np.random.default_rng(4)
    for _ in range(63):
        close.append(close[-1] * (1.0 + rng.normal(0, 0.006)))
    for _ in range(5):
        close.append(close[-1] * (1.0 + rng.normal(0, 0.05)))  # spike -> closes
    for _ in range(80):
        close.append(close[-1] * (1.0 + rng.normal(0, 0.004)))  # genuinely calm -> reopens
    gate = vah._vol_accel_hysteresis_gate(
        close, short_window=5, long_window=63, exit_threshold=1.75, reentry_threshold=1.25
    )
    assert gate[-1] == 1.0, "sustained calm must eventually reopen the gate"


def test_gate_zeroes_out_the_base_signal_when_closed():
    close = [100.0]
    for _ in range(299):
        close.append(close[-1] * (1.0 + 0.001))
    for swing in (0.10, -0.12, 0.09, -0.11, 0.08):
        close.append(close[-1] * (1.0 + swing))
    bars = bars_from_close(close)
    sig = vah.Signal()
    out = sig.generate(bars)
    base = sig._base.generate(bars)
    assert base["SPY"].iloc[-1] == 1.0, "base trend signal is still long"
    assert out["SPY"].iloc[-1] == 0.0, "hysteresis gate must override it to flat"


def test_invalid_params_raise():
    with pytest.raises(ValueError):
        vah.Signal(vol_short_window=1)
    with pytest.raises(ValueError):
        vah.Signal(vol_short_window=10, vol_long_window=10)
    with pytest.raises(ValueError):
        vah.Signal(vol_accel_reentry_threshold=1.0)
    with pytest.raises(ValueError):
        vah.Signal(vol_accel_exit_threshold=1.2, vol_accel_reentry_threshold=1.25)


def test_lookahead_safe_on_random_close():
    rng = np.random.default_rng(13)
    n = 400
    close = 100 * np.exp(np.cumsum(rng.normal(0.0003, 0.012, n)))
    bars = bars_from_close(list(close))
    sig = vah.Signal()
    out = generate_checked(sig, bars)  # raises LookaheadError on any leak
    assert set(np.unique(out.to_numpy())) <= {0.0, 1.0}


def test_export_params_roundtrips_shape():
    sig = vah.Signal(
        lookback=252, skip=21, vol_short_window=5, vol_long_window=63,
        vol_accel_exit_threshold=1.75, vol_accel_reentry_threshold=1.25,
    )
    assert sig.export_params() == {
        "type": "tsmom_vol_accel_hysteresis",
        "lookback": 252,
        "skip": 21,
        "vol_short_window": 5,
        "vol_long_window": 63,
        "vol_accel_exit_threshold": 1.75,
        "vol_accel_reentry_threshold": 1.25,
    }
