"""Unit tests for the dual-momentum signal: warm-up flatness, relative-leader
selection, the absolute floor (goes flat when even the leader is negative),
holds constant within a month, invalid params, and lookahead safety through
the harness guard."""

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from backtest.signal import BarFrame, generate_checked

_spec = importlib.util.spec_from_file_location(
    "dual_momentum_equity_bond_gold",
    Path(__file__).resolve().parents[1] / "strategies/dual_momentum_equity_bond_gold.py",
)
dm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dm)


def bars_from_close_dict(close: dict[str, list[float]], start="2016-01-01") -> BarFrame:
    n = len(next(iter(close.values())))
    idx = pd.bdate_range(start, periods=n)
    mk = lambda: pd.DataFrame(close, index=idx)
    return BarFrame(open=mk(), high=mk(), low=mk(), close=mk())


def _drift_series(n: int, daily_ret: float, start_price: float = 100.0) -> list[float]:
    close = [start_price]
    for _ in range(n - 1):
        close.append(close[-1] * (1.0 + daily_ret))
    return close


def test_insufficient_history_is_flat():
    n = 200  # fewer than skip+lookback=273
    close = {sym: _drift_series(n, 0.001) for sym in ["SPY", "TLT", "GLD"]}
    bars = bars_from_close_dict(close)
    sig = dm.Signal(lookback=252, skip=21)
    out = generate_checked(sig, bars)
    assert (out == 0.0).to_numpy().all()


def test_holds_the_relative_leader_when_it_clears_the_floor():
    n = 320
    close = {
        "SPY": _drift_series(n, 0.002),
        "TLT": _drift_series(n, 0.0005),
        "GLD": _drift_series(n, -0.001),
    }
    bars = bars_from_close_dict(close)
    sig = dm.Signal(lookback=252, skip=21)
    out = generate_checked(sig, bars)
    last = out.iloc[-1]
    assert last["SPY"] == 1.0
    assert last["TLT"] == 0.0
    assert last["GLD"] == 0.0
    assert last.sum() == 1.0


def test_goes_flat_when_even_the_leader_is_negative():
    # All three trend down; SPY is the "least bad" (relative leader) but
    # its own trailing momentum is still negative -- the absolute floor
    # must override the relative rank and go flat, unlike sector_rotation
    # which would still hold the least-bad candidate.
    n = 320
    close = {
        "SPY": _drift_series(n, -0.0005),
        "TLT": _drift_series(n, -0.0015),
        "GLD": _drift_series(n, -0.0025),
    }
    bars = bars_from_close_dict(close)
    sig = dm.Signal(lookback=252, skip=21)
    out = generate_checked(sig, bars)
    assert (out.iloc[-1] == 0.0).all()


def test_selection_holds_constant_within_a_month():
    n = 330
    rng = np.random.default_rng(5)
    close = {
        sym: list(100 * np.exp(np.cumsum(rng.normal(0.0005 * mult, 0.01, n))))
        for sym, mult in [("SPY", 2), ("TLT", 1), ("GLD", -1)]
    }
    bars = bars_from_close_dict(close)
    sig = dm.Signal(lookback=252, skip=21)
    out = sig.generate(bars)

    idx = out.index
    for t in range(280, n - 1):
        if (idx[t].year, idx[t].month) == (idx[t + 1].year, idx[t + 1].month):
            assert out.iloc[t].tolist() == out.iloc[t + 1].tolist(), (
                "weights must not change between two days in the same calendar month"
            )
            break
    else:
        raise AssertionError("no same-month consecutive pair found in range -- test setup bug")


def test_invalid_params_raise():
    with pytest.raises(ValueError):
        dm.Signal(lookback=1)
    with pytest.raises(ValueError):
        dm.Signal(lookback=252, skip=252)


def test_lookahead_safe_on_random_multi_symbol_close():
    rng = np.random.default_rng(29)
    n = 400
    close = {
        sym: list(100 * np.exp(np.cumsum(rng.normal(0.0003, 0.012, n))))
        for sym in ["SPY", "TLT", "GLD"]
    }
    bars = bars_from_close_dict(close)
    sig = dm.Signal(lookback=252, skip=21)
    out = generate_checked(sig, bars)  # raises LookaheadError on any leak
    assert ((out == 0.0) | (out == 1.0)).to_numpy().all()
    assert (out.sum(axis=1) <= 1.0).all()


def test_export_params_roundtrips_shape():
    sig = dm.Signal(lookback=252, skip=21)
    assert sig.export_params() == {
        "type": "dual_momentum",
        "lookback": 252,
        "skip": 21,
    }
