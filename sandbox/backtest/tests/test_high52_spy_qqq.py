"""Unit tests for the 52-week-high-proximity signal: warm-up flatness,
triggers near a new high, stays flat well below the high, invalid
params, and lookahead safety through the harness guard."""

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from backtest.signal import BarFrame, generate_checked

_spec = importlib.util.spec_from_file_location(
    "high52_spy_qqq",
    Path(__file__).resolve().parents[1] / "strategies/high52_spy_qqq.py",
)
h52 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(h52)


def bars_from_close(close: list[float]) -> BarFrame:
    idx = pd.bdate_range("2016-01-01", periods=len(close))
    mk = lambda v: pd.DataFrame({"SPY": v}, index=idx)
    return BarFrame(open=mk(close), high=mk(close), low=mk(close), close=mk(close))


def test_insufficient_history_is_flat():
    close = [100.0] * 200  # fewer than the 252-session lookback
    bars = bars_from_close(close)
    sig = h52.Signal(lookback=252, nearness_threshold=0.95)
    out = generate_checked(sig, bars)
    assert (out["SPY"] == 0.0).all()


def test_at_a_new_high_is_long():
    close = [100.0 + i * 0.1 for i in range(300)]  # strictly rising -> always at its own high
    bars = bars_from_close(close)
    sig = h52.Signal(lookback=252, nearness_threshold=0.95)
    out = generate_checked(sig, bars)
    assert out["SPY"].iloc[-1] == 1.0
    assert out["SPY"].iloc[251:].eq(1.0).all(), "always exactly at its own trailing high"


def test_well_below_the_high_is_flat():
    close = [100.0 + i * 0.1 for i in range(280)]  # rally to a high...
    peak = close[-1]
    close += [peak * 0.7] * 20  # ...then a sharp drop, well outside the 5% band
    bars = bars_from_close(close)
    sig = h52.Signal(lookback=252, nearness_threshold=0.95)
    out = generate_checked(sig, bars)
    assert out["SPY"].iloc[-1] == 0.0


def test_threshold_boundary():
    close = [100.0] * 252 + [96.0]  # 96/100 = 0.96 >= 0.95 threshold
    bars = bars_from_close(close)
    sig = h52.Signal(lookback=252, nearness_threshold=0.95)
    out = generate_checked(sig, bars)
    assert out["SPY"].iloc[-1] == 1.0
    close2 = [100.0] * 252 + [94.0]  # 94/100 = 0.94 < 0.95 threshold
    bars2 = bars_from_close(close2)
    out2 = generate_checked(sig, bars2)
    assert out2["SPY"].iloc[-1] == 0.0


def test_invalid_params_raise():
    with pytest.raises(ValueError):
        h52.Signal(lookback=1)
    with pytest.raises(ValueError):
        h52.Signal(nearness_threshold=0.0)
    with pytest.raises(ValueError):
        h52.Signal(nearness_threshold=1.1)


def test_lookahead_safe_on_random_close():
    rng = np.random.default_rng(19)
    n = 400
    close = 100 * np.exp(np.cumsum(rng.normal(0.0003, 0.012, n)))
    bars = bars_from_close(list(close))
    sig = h52.Signal()
    out = generate_checked(sig, bars)  # raises LookaheadError on any leak
    assert set(np.unique(out.to_numpy())) <= {0.0, 1.0}


def test_export_params_roundtrips_shape():
    sig = h52.Signal(lookback=252, nearness_threshold=0.95)
    assert sig.export_params() == {
        "type": "high52",
        "lookback": 252,
        "nearness_threshold": 0.95,
    }
