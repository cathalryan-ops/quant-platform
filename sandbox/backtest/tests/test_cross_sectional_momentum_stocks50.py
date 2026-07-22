"""Unit tests for the cross-sectional-momentum-stocks50 wrapper: confirms
it delegates to sector_rotation.Signal unmodified with the
concentration-adjusted top_n default (15, not sector-rotation's 3), and
that lookahead safety holds through the harness guard."""

import importlib.util
from pathlib import Path

import numpy as np
import pytest

from backtest.signal import BarFrame, generate_checked

_spec = importlib.util.spec_from_file_location(
    "cross_sectional_momentum_stocks50",
    Path(__file__).resolve().parents[1] / "strategies/cross_sectional_momentum_stocks50.py",
)
csm50 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(csm50)


def bars_from_close_dict(close: dict[str, list[float]], start="2016-01-01") -> BarFrame:
    import pandas as pd

    n = len(next(iter(close.values())))
    idx = pd.bdate_range(start, periods=n)
    mk = lambda: pd.DataFrame(close, index=idx)
    return BarFrame(open=mk(), high=mk(), low=mk(), close=mk())


def _drift_series(n: int, daily_ret: float, start_price: float = 100.0) -> list[float]:
    close = [start_price]
    for _ in range(n - 1):
        close.append(close[-1] * (1.0 + daily_ret))
    return close


def test_defaults_are_concentration_adjusted_not_sector_rotation_defaults():
    sig = csm50.Signal()
    assert (sig.lookback, sig.skip, sig.top_n) == (252, 21, 15)


def test_top_n_selects_the_strongest_of_many():
    n = 320
    close = {f"SYM{i}": _drift_series(n, 0.003 - i * 0.0005) for i in range(20)}
    bars = bars_from_close_dict(close)
    sig = csm50.Signal(top_n=5)
    out = generate_checked(sig, bars)
    last = out.iloc[-1]
    assert last.sum() == 5.0
    top5 = sorted(range(20), key=lambda i: -(0.003 - i * 0.0005))[:5]
    for i in top5:
        assert last[f"SYM{i}"] == 1.0


def test_lookahead_safe_on_random_multi_symbol_close():
    rng = np.random.default_rng(7)
    n = 400
    close = {
        sym: list(100 * np.exp(np.cumsum(rng.normal(0.0003, 0.012, n))))
        for sym in [f"SYM{i}" for i in range(10)]
    }
    bars = bars_from_close_dict(close)
    sig = csm50.Signal(top_n=3)
    out = generate_checked(sig, bars)  # raises LookaheadError on any leak
    assert ((out == 0.0) | (out == 1.0)).to_numpy().all()


def test_custom_params_still_delegate_correctly():
    n = 300
    close = {sym: _drift_series(n, 0.003 if sym == "A" else -0.001) for sym in ["A", "B", "C"]}
    bars = bars_from_close_dict(close)
    sig = csm50.Signal(lookback=252, skip=21, top_n=1)
    out = generate_checked(sig, bars)
    assert out.iloc[-1]["A"] == 1.0
    assert out.iloc[-1].sum() == 1.0


def test_invalid_top_n_raises():
    with pytest.raises(ValueError):
        csm50.Signal(top_n=0)


def test_export_params_roundtrips_shape():
    sig = csm50.Signal(lookback=252, skip=21, top_n=15)
    assert sig.export_params() == {
        "type": "cross_sectional_momentum_stocks50",
        "lookback": 252,
        "skip": 21,
        "top_n": 15,
    }
