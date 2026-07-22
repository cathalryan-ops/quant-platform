"""Unit tests for the low-volatility-anomaly signal: warm-up flatness,
correct low-vol (not high-vol) ranking, holds constant within a month and
only re-ranks on month boundaries, invalid params, and lookahead safety
through the harness guard."""

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from backtest.signal import BarFrame, generate_checked

_spec = importlib.util.spec_from_file_location(
    "low_vol_anomaly_stocks50",
    Path(__file__).resolve().parents[1] / "strategies/low_vol_anomaly_stocks50.py",
)
lva = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lva)


def bars_from_close_dict(close: dict[str, list[float]], start="2016-01-01") -> BarFrame:
    n = len(next(iter(close.values())))
    idx = pd.bdate_range(start, periods=n)
    mk = lambda: pd.DataFrame(close, index=idx)
    return BarFrame(open=mk(), high=mk(), low=mk(), close=mk())


def _const_vol_series(n: int, daily_vol: float, seed: int, drift: float = 0.0005) -> list[float]:
    rng = np.random.default_rng(seed)
    return list(100 * np.exp(np.cumsum(rng.normal(drift, daily_vol, n))))


def test_insufficient_history_is_flat():
    n = 200  # fewer than lookback=252
    close = {sym: _const_vol_series(n, 0.01, seed=i) for i, sym in enumerate(["A", "B", "C", "D"])}
    bars = bars_from_close_dict(close)
    sig = lva.Signal(lookback=252, top_n=2)
    out = generate_checked(sig, bars)
    assert (out == 0.0).to_numpy().all()


def test_top_n_selects_the_least_volatile_not_the_strongest():
    n = 320
    close = {
        "CALM": _const_vol_series(n, 0.003, seed=1, drift=0.0002),
        "MILD": _const_vol_series(n, 0.008, seed=2, drift=0.0002),
        "WILD": _const_vol_series(n, 0.02, seed=3, drift=0.0002),
        "WILDEST": _const_vol_series(n, 0.04, seed=4, drift=0.0002),
    }
    bars = bars_from_close_dict(close)
    sig = lva.Signal(lookback=252, top_n=2)
    out = generate_checked(sig, bars)
    last = out.iloc[-1]
    assert last["CALM"] == 1.0
    assert last["MILD"] == 1.0
    assert last["WILD"] == 0.0
    assert last["WILDEST"] == 0.0
    assert last.sum() == 2.0


def test_selection_holds_constant_within_a_month():
    n = 330
    rng = np.random.default_rng(3)
    close = {
        sym: list(100 * np.exp(np.cumsum(rng.normal(0.0003, vol, n))))
        for sym, vol in [("A", 0.005), ("B", 0.01), ("C", 0.02), ("D", 0.035)]
    }
    bars = bars_from_close_dict(close)
    sig = lva.Signal(lookback=252, top_n=2)
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
        lva.Signal(lookback=1)
    with pytest.raises(ValueError):
        lva.Signal(top_n=0)


def test_top_n_larger_than_universe_raises():
    close = {sym: _const_vol_series(50, 0.01, seed=i) for i, sym in enumerate(["A", "B"])}
    bars = bars_from_close_dict(close)
    sig = lva.Signal(top_n=3)
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
    sig = lva.Signal(lookback=252, top_n=2)
    out = generate_checked(sig, bars)  # raises LookaheadError on any leak
    assert ((out == 0.0) | (out == 1.0)).to_numpy().all()


def test_export_params_roundtrips_shape():
    sig = lva.Signal(lookback=252, top_n=15)
    assert sig.export_params() == {
        "type": "low_vol_anomaly",
        "lookback": 252,
        "top_n": 15,
    }
