"""Unit tests for the vol-targeted tsmom signal: the scaling factor
itself, that it's capped at 1.0 (never levers up), that it shrinks
smoothly (no threshold) as vol rises, that it correctly scales the base
signal, invalid params, and lookahead safety through the harness guard."""

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from backtest.signal import BarFrame, generate_checked

_spec = importlib.util.spec_from_file_location(
    "tsmom_vol_target",
    Path(__file__).resolve().parents[1] / "strategies/tsmom_vol_target.py",
)
vt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vt)


def bars_from_close(close: list[float]) -> BarFrame:
    idx = pd.bdate_range("2016-01-01", periods=len(close))
    mk = lambda v: pd.DataFrame({"SPY": v}, index=idx)
    return BarFrame(open=mk(close), high=mk(close), low=mk(close), close=mk(close))


def test_scalar_zero_during_warmup_and_on_flat_prices():
    close = [100.0] * 40
    scalar = vt._vol_target_scalar(close, window=20, vol_target=0.15)
    assert all(s == 0.0 for s in scalar), "no realized vol yet estimable anywhere -> 0.0"


def test_scalar_capped_at_one_in_calm_markets():
    rng = np.random.default_rng(2)
    # ~0.006 daily std annualizes to ~0.006*sqrt(252) ~= 0.095, well under
    # a 0.15 target -- the ratio would exceed 1.0 without the cap.
    close = [100.0]
    for _ in range(60):
        close.append(close[-1] * (1.0 + rng.normal(0, 0.006)))
    scalar = vt._vol_target_scalar(close, window=20, vol_target=0.15)
    assert all(s <= 1.0 for s in scalar)
    assert any(s == 1.0 for s in scalar[20:]), "calm vol should hit the 1.0 cap, never exceed it"


def test_scalar_shrinks_smoothly_as_vol_rises():
    # Two vol regimes back to back: calm, then persistently more volatile
    # (but not violently so). The scalar should be monotonically lower in
    # the high-vol regime once the window has rolled fully into it, and it
    # should move gradually, not jump discretely at any single point --
    # the entire structural point of a continuous scalar over a gate.
    rng = np.random.default_rng(6)
    close = [100.0]
    for _ in range(60):
        close.append(close[-1] * (1.0 + rng.normal(0, 0.004)))  # calm
    for _ in range(60):
        close.append(close[-1] * (1.0 + rng.normal(0, 0.02)))  # elevated
    scalar = vt._vol_target_scalar(close, window=20, vol_target=0.15)
    calm_avg = sum(scalar[40:60]) / 20
    elevated_avg = sum(scalar[100:120]) / 20
    assert elevated_avg < calm_avg, "scalar should be lower once the window is fully in the elevated regime"
    # No single-session jump larger than a plausible one-day rolling-window
    # update -- i.e. it's a smooth glide, not a step function.
    diffs = [abs(scalar[i] - scalar[i - 1]) for i in range(61, 121)]
    assert max(diffs) < 0.5, "no single day should swing the scalar by a huge discrete jump"


def test_signal_scales_the_base_weight():
    close = [100.0]
    for _ in range(299):
        close.append(close[-1] * (1.0 + 0.001))
    rng = np.random.default_rng(1)
    for _ in range(20):
        close.append(close[-1] * (1.0 + rng.normal(0.001, 0.03)))  # elevated vol, still uptrend
    bars = bars_from_close(close)
    sig = vt.Signal(lookback=252, skip=21, vol_window=20, vol_target=0.15)
    out = sig.generate(bars)
    base = sig._base.generate(bars)
    assert base["SPY"].iloc[-1] == 1.0, "base trend signal is still long"
    assert 0.0 < out["SPY"].iloc[-1] < 1.0, "elevated vol should scale the position down, not to zero or full"


def test_invalid_params_raise():
    with pytest.raises(ValueError):
        vt.Signal(vol_window=1)
    with pytest.raises(ValueError):
        vt.Signal(vol_target=0.0)
    with pytest.raises(ValueError):
        vt.Signal(vol_target=-0.1)


def test_lookahead_safe_on_random_close():
    rng = np.random.default_rng(17)
    n = 400
    close = 100 * np.exp(np.cumsum(rng.normal(0.0003, 0.012, n)))
    bars = bars_from_close(list(close))
    sig = vt.Signal()
    out = generate_checked(sig, bars)  # raises LookaheadError on any leak
    assert ((out >= 0.0) & (out <= 1.0)).all().all()


def test_export_params_roundtrips_shape():
    sig = vt.Signal(lookback=252, skip=21, vol_window=20, vol_target=0.15)
    assert sig.export_params() == {
        "type": "tsmom_vol_target",
        "lookback": 252,
        "skip": 21,
        "vol_window": 20,
        "vol_target": 0.15,
    }
