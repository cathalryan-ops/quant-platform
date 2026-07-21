"""Unit tests for the time-series momentum signal: sign detection, warm-up
flatness, invalid params, and -- critically -- lookahead safety through the
harness guard."""

import importlib.util
from pathlib import Path

import pandas as pd
import pytest

from backtest.signal import BarFrame, generate_checked

_spec = importlib.util.spec_from_file_location(
    "tsmom_spy_qqq",
    Path(__file__).resolve().parents[1] / "strategies/tsmom_spy_qqq.py",
)
tsmom = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tsmom)


def bars_from_close(close: dict[str, list[float]]) -> BarFrame:
    n = len(next(iter(close.values())))
    idx = pd.bdate_range("2016-01-01", periods=n)
    mk = lambda col: pd.DataFrame({sym: v for sym, v in col.items()}, index=idx)
    return BarFrame(open=mk(close), high=mk(close), low=mk(close), close=mk(close))


def _up_then_flat(n: int, up_days: int, daily_ret: float = 0.002) -> list[float]:
    close = [100.0]
    for i in range(1, n):
        r = daily_ret if i <= up_days else 0.0
        close.append(close[-1] * (1.0 + r))
    return close


def test_insufficient_history_is_flat():
    # Fewer bars than skip + lookback anywhere in the series -> always flat.
    close = _up_then_flat(100, up_days=100)
    sig = tsmom.Signal(lookback=252, skip=21)
    bars = bars_from_close({"SPY": close})
    w = generate_checked(sig, bars)
    assert (w["SPY"] == 0.0).all()


def test_sustained_uptrend_goes_long_after_warmup():
    # 300 sessions of steady positive drift: by session 273 (skip=21 +
    # lookback=252), the trailing-12-month-ending-1-month-ago return is
    # unambiguously positive.
    close = _up_then_flat(300, up_days=300, daily_ret=0.001)
    sig = tsmom.Signal(lookback=252, skip=21)
    bars = bars_from_close({"SPY": close})
    w = generate_checked(sig, bars)
    assert w["SPY"].iloc[273] == 1.0, "first session with a full skip+lookback window"
    assert w["SPY"].iloc[:273].eq(0.0).all(), "flat during the warm-up window"


def test_sustained_downtrend_stays_flat():
    close = [100.0]
    for _ in range(299):
        close.append(close[-1] * (1.0 - 0.001))
    sig = tsmom.Signal(lookback=252, skip=21)
    bars = bars_from_close({"SPY": close})
    w = generate_checked(sig, bars)
    assert (w["SPY"] == 0.0).all(), "negative trailing momentum never goes long"


def test_two_symbols_scored_independently():
    up = _up_then_flat(300, up_days=300, daily_ret=0.001)
    down = [100.0]
    for _ in range(299):
        down.append(down[-1] * (1.0 - 0.001))
    sig = tsmom.Signal(lookback=252, skip=21)
    bars = bars_from_close({"SPY": up, "QQQ": down})
    w = generate_checked(sig, bars)
    assert w["SPY"].iloc[273] == 1.0
    assert w["QQQ"].iloc[273] == 0.0


def test_weights_bounded_zero_one():
    close = _up_then_flat(300, up_days=150, daily_ret=0.003)
    sig = tsmom.Signal(lookback=252, skip=21)
    bars = bars_from_close({"SPY": close})
    w = generate_checked(sig, bars)
    assert w["SPY"].isin([0.0, 1.0]).all()


def test_invalid_params_raise():
    with pytest.raises(ValueError):
        tsmom.Signal(lookback=1)
    with pytest.raises(ValueError):
        tsmom.Signal(skip=-1)
    with pytest.raises(ValueError):
        tsmom.Signal(lookback=252, skip=252)
