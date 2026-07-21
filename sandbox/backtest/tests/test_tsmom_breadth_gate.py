"""Unit tests for the breadth-gated tsmom signal: the gate correctly zeroes
out the base signal when sector participation is narrow, holds it when
participation is broad, never trades the breadth symbols themselves,
invalid params, and lookahead safety through the harness guard."""

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from backtest.signal import BarFrame, generate_checked

_spec = importlib.util.spec_from_file_location(
    "tsmom_breadth_gate",
    Path(__file__).resolve().parents[1] / "strategies/tsmom_breadth_gate.py",
)
bg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bg)


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
    close = {sym: _drift_series(n, 0.001) for sym in ["SPY", "QQQ", "S1", "S2", "S3", "S4"]}
    bars = bars_from_close_dict(close)
    sig = bg.Signal(lookback=252, skip=21, trade_symbols=("SPY", "QQQ"))
    out = generate_checked(sig, bars)
    assert (out == 0.0).to_numpy().all()


def test_gate_open_when_breadth_is_broad():
    n = 320
    close = {
        "SPY": _drift_series(n, 0.002),
        "QQQ": _drift_series(n, 0.002),
        "S1": _drift_series(n, 0.001),
        "S2": _drift_series(n, 0.001),
        "S3": _drift_series(n, 0.001),
        "S4": _drift_series(n, -0.0005),  # only one of four sectors lagging: breadth 75%
    }
    bars = bars_from_close_dict(close)
    sig = bg.Signal(lookback=252, skip=21, breadth_threshold=0.5, trade_symbols=("SPY", "QQQ"))
    out = generate_checked(sig, bars)
    assert out["SPY"].iloc[-1] == 1.0
    assert out["QQQ"].iloc[-1] == 1.0


def test_gate_closes_when_breadth_is_narrow_even_if_trade_symbol_is_up():
    n = 320
    close = {
        "SPY": _drift_series(n, 0.002),  # SPY itself unambiguously trending up
        "QQQ": _drift_series(n, 0.002),
        "S1": _drift_series(n, -0.001),
        "S2": _drift_series(n, -0.001),
        "S3": _drift_series(n, -0.001),
        "S4": _drift_series(n, -0.001),  # 0 of 4 sectors up: breadth 0%
    }
    bars = bars_from_close_dict(close)
    sig = bg.Signal(lookback=252, skip=21, breadth_threshold=0.5, trade_symbols=("SPY", "QQQ"))
    out = generate_checked(sig, bars)
    base = sig._base.generate(bars)
    assert base["SPY"].iloc[-1] == 1.0, "base trend signal is still long"
    assert out["SPY"].iloc[-1] == 0.0, "narrow breadth must override it to flat"
    assert out["QQQ"].iloc[-1] == 0.0


def test_breadth_symbols_never_get_nonzero_weight():
    n = 320
    close = {
        "SPY": _drift_series(n, 0.002),
        "QQQ": _drift_series(n, 0.002),
        "S1": _drift_series(n, 0.003),
        "S2": _drift_series(n, 0.003),
    }
    bars = bars_from_close_dict(close)
    sig = bg.Signal(lookback=252, skip=21, breadth_threshold=0.5, trade_symbols=("SPY", "QQQ"))
    out = generate_checked(sig, bars)
    assert (out["S1"] == 0.0).all()
    assert (out["S2"] == 0.0).all()


def test_invalid_params_raise():
    with pytest.raises(ValueError):
        bg.Signal(breadth_threshold=0.0)
    with pytest.raises(ValueError):
        bg.Signal(breadth_threshold=1.5)
    with pytest.raises(ValueError):
        bg.Signal(trade_symbols=())


def test_no_breadth_symbols_raises():
    n = 320
    close = {"SPY": _drift_series(n, 0.001), "QQQ": _drift_series(n, 0.001)}
    bars = bars_from_close_dict(close)
    sig = bg.Signal(trade_symbols=("SPY", "QQQ"))
    with pytest.raises(ValueError):
        sig.generate(bars)


def test_lookahead_safe_on_random_multi_symbol_close():
    rng = np.random.default_rng(41)
    n = 400
    close = {
        sym: list(100 * np.exp(np.cumsum(rng.normal(0.0003, 0.012, n))))
        for sym in ["SPY", "QQQ", "S1", "S2", "S3", "S4", "S5"]
    }
    bars = bars_from_close_dict(close)
    sig = bg.Signal(lookback=252, skip=21, breadth_threshold=0.5, trade_symbols=("SPY", "QQQ"))
    out = generate_checked(sig, bars)  # raises LookaheadError on any leak
    assert set(np.unique(out.to_numpy())) <= {0.0, 1.0}


def test_export_params_roundtrips_shape():
    sig = bg.Signal(lookback=252, skip=21, breadth_threshold=0.5, trade_symbols=("SPY", "QQQ"))
    assert sig.export_params() == {
        "type": "tsmom_breadth_gate",
        "lookback": 252,
        "skip": 21,
        "breadth_threshold": 0.5,
        "trade_symbols": ["SPY", "QQQ"],
    }
