"""Unit tests for the pairs-trading/stat-arb signal: warm-up flatness,
entry direction (long the cheap leg / short the rich leg), exit on
convergence, the max-hold safety exit, invalid params, and lookahead
safety through the harness guard."""

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from backtest.signal import BarFrame, generate_checked

_spec = importlib.util.spec_from_file_location(
    "pairs_trading_stocks50",
    Path(__file__).resolve().parents[1] / "strategies/pairs_trading_stocks50.py",
)
pt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pt)


def bars_from_close_dict(close: dict[str, list[float]], start="2016-01-01") -> BarFrame:
    n = len(next(iter(close.values())))
    idx = pd.bdate_range(start, periods=n)
    mk = lambda: pd.DataFrame(close, index=idx)
    return BarFrame(open=mk(), high=mk(), low=mk(), close=mk())


# --- _pair_weights: the state machine tested directly against an explicit
# z/beta path. The full Signal's rolling beta reacts to the same window a
# price shock lands in, which confounds "does A rise relative to B" with
# "what does the adaptive hedge ratio do" -- exercising the state machine
# on a hand-specified z path isolates entry/exit/hold logic cleanly. The
# rolling-beta/spread machinery itself is covered by
# test_insufficient_history_is_flat (warm-up) and the lookahead guard
# below, both of which only depend on the full pipeline's shape, not on a
# particular z sign at a particular day. ---


def test_state_machine_enters_long_spread_when_z_very_negative():
    z = [0.0, 0.0, -2.5, -2.5, -2.5]
    beta = [1.0] * len(z)
    wa, wb = pt._pair_weights(z, beta, entry_z=2.0, exit_z=0.5, max_hold_days=20)
    assert wa == [0.0, 0.0, 1.0, 1.0, 1.0]
    assert wb == [0.0, 0.0, -1.0, -1.0, -1.0]


def test_state_machine_enters_short_spread_when_z_very_positive():
    z = [0.0, 0.0, 2.5, 2.5, 2.5]
    beta = [0.8] * len(z)
    wa, wb = pt._pair_weights(z, beta, entry_z=2.0, exit_z=0.5, max_hold_days=20)
    assert wa == [0.0, 0.0, -1.0, -1.0, -1.0]
    assert wb == [0.0, 0.0, 0.8, 0.8, 0.8]


def test_state_machine_exits_on_convergence():
    z = [0.0, 2.5, 2.5, 2.5, 0.3, 0.3]
    beta = [1.0] * len(z)
    wa, _ = pt._pair_weights(z, beta, entry_z=2.0, exit_z=0.5, max_hold_days=20)
    # In (short spread) at index 1, converges (|z|<=0.5) at index 4 -- must
    # be flat from index 4 onward.
    assert wa == [0.0, -1.0, -1.0, -1.0, 0.0, 0.0]


def test_state_machine_max_hold_forces_exit_without_convergence():
    z = [0.0] + [2.5] * 12  # never converges
    beta = [1.0] * len(z)
    wa, _ = pt._pair_weights(z, beta, entry_z=2.0, exit_z=0.5, max_hold_days=5)
    # Entry at index 1, forced flat once held for max_hold_days=5 sessions.
    assert wa == [0.0, -1.0, -1.0, -1.0, -1.0, -1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]


def test_state_machine_nan_forces_flat_and_does_not_reenter_spuriously():
    z = [float("nan"), float("nan"), -2.5, -2.5]
    beta = [float("nan"), 1.0, 1.0, 1.0]
    wa, wb = pt._pair_weights(z, beta, entry_z=2.0, exit_z=0.5, max_hold_days=20)
    assert wa == [0.0, 0.0, 1.0, 1.0]
    assert wb == [0.0, 0.0, -1.0, -1.0]


def test_insufficient_history_is_flat():
    n = 50  # fewer than hedge_lookback=zscore_lookback=60
    close = {"A": [100.0 + 0.01 * t for t in range(n)], "B": [50.0 + 0.005 * t for t in range(n)]}
    bars = bars_from_close_dict(close)
    sig = pt.Signal(pairs=(("A", "B"),), hedge_lookback=60, zscore_lookback=60)
    out = generate_checked(sig, bars)
    assert (out == 0.0).to_numpy().all()


def test_invalid_params_raise():
    with pytest.raises(ValueError):
        pt.Signal(hedge_lookback=1)
    with pytest.raises(ValueError):
        pt.Signal(zscore_lookback=1)
    with pytest.raises(ValueError):
        pt.Signal(entry_z=0.5, exit_z=0.5)
    with pytest.raises(ValueError):
        pt.Signal(exit_z=-1.0)
    with pytest.raises(ValueError):
        pt.Signal(max_hold_days=0)


def test_lookahead_safe_on_random_multi_pair_close():
    rng = np.random.default_rng(23)
    n = 300
    close = {
        sym: list(100 * np.exp(np.cumsum(rng.normal(0.0003, 0.012, n))))
        for sym in ["A", "B", "C", "D"]
    }
    bars = bars_from_close_dict(close)
    sig = pt.Signal(pairs=(("A", "B"), ("C", "D")), hedge_lookback=60, zscore_lookback=60)
    generate_checked(sig, bars)  # raises LookaheadError on any leak


def test_export_params_roundtrips_shape():
    sig = pt.Signal(pairs=(("A", "B"),), hedge_lookback=60, zscore_lookback=60)
    assert sig.export_params() == {
        "type": "pairs_trading",
        "pairs": [["A", "B"]],
        "hedge_lookback": 60,
        "zscore_lookback": 60,
        "entry_z": 2.0,
        "exit_z": 0.5,
        "max_hold_days": 20,
        "beta_min": 0.1,
        "beta_max": 3.0,
    }
