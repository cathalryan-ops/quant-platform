"""Unit tests for the cross-sectional sector-rotation signal: warm-up
flatness, correct top-N ranking, holds constant within a month and only
re-ranks on month boundaries, invalid params, and lookahead safety
through the harness guard."""

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from backtest.signal import BarFrame, generate_checked

_spec = importlib.util.spec_from_file_location(
    "sector_rotation",
    Path(__file__).resolve().parents[1] / "strategies/sector_rotation.py",
)
sr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sr)


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
    close = {sym: _drift_series(n, 0.001) for sym in ["A", "B", "C", "D"]}
    bars = bars_from_close_dict(close)
    sig = sr.Signal(lookback=252, skip=21, top_n=2)
    out = generate_checked(sig, bars)
    assert (out == 0.0).to_numpy().all()


def test_top_n_selects_the_strongest_trailing_momentum():
    n = 320
    close = {
        "STRONG": _drift_series(n, 0.003),
        "MID": _drift_series(n, 0.001),
        "WEAK": _drift_series(n, -0.001),
        "WEAKEST": _drift_series(n, -0.003),
    }
    bars = bars_from_close_dict(close)
    sig = sr.Signal(lookback=252, skip=21, top_n=2)
    out = generate_checked(sig, bars)
    last = out.iloc[-1]
    assert last["STRONG"] == 1.0
    assert last["MID"] == 1.0
    assert last["WEAK"] == 0.0
    assert last["WEAKEST"] == 0.0
    assert last.sum() == 2.0


def test_selection_holds_constant_within_a_month():
    # Build a series long enough to reach a stable ranking, then check
    # that the weight doesn't change on non-rebalance (non-month-boundary)
    # days even as prices keep moving -- only the calendar triggers a
    # re-rank, not a "did the ranking change" check.
    n = 330
    rng = np.random.default_rng(3)
    close = {
        sym: list(100 * np.exp(np.cumsum(rng.normal(0.0005 * mult, 0.01, n))))
        for sym, mult in [("A", 3), ("B", 1), ("C", -1), ("D", -3)]
    }
    bars = bars_from_close_dict(close)
    sig = sr.Signal(lookback=252, skip=21, top_n=2)
    out = sig.generate(bars)

    # Find two consecutive days in the same calendar month, both well past
    # warm-up, and confirm the selection is identical.
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
        sr.Signal(lookback=1)
    with pytest.raises(ValueError):
        sr.Signal(lookback=252, skip=252)
    with pytest.raises(ValueError):
        sr.Signal(top_n=0)


def test_top_n_larger_than_universe_raises():
    close = {sym: _drift_series(50, 0.001) for sym in ["A", "B"]}
    bars = bars_from_close_dict(close)
    sig = sr.Signal(top_n=3)
    with pytest.raises(ValueError):
        sig.generate(bars)


def test_lookahead_safe_on_random_multi_symbol_close():
    rng = np.random.default_rng(23)
    n = 400
    close = {
        sym: list(100 * np.exp(np.cumsum(rng.normal(0.0003, 0.012, n))))
        for sym in ["A", "B", "C", "D", "E"]
    }
    bars = bars_from_close_dict(close)
    sig = sr.Signal(lookback=252, skip=21, top_n=2)
    out = generate_checked(sig, bars)  # raises LookaheadError on any leak
    assert ((out == 0.0) | (out == 1.0)).to_numpy().all()


def test_export_params_roundtrips_shape():
    sig = sr.Signal(lookback=252, skip=21, top_n=3)
    assert sig.export_params() == {
        "type": "sector_rotation",
        "lookback": 252,
        "skip": 21,
        "top_n": 3,
    }
