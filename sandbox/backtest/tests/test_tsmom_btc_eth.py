"""Unit tests for the crypto tsmom wrapper: confirms it delegates to
tsmom_spy_qqq.Signal unmodified with the calendar-adjusted lookback/skip
defaults (365/30, not equities' 252/21), and that lookahead safety holds
through the harness guard on 365-day-per-year bars."""

import importlib.util
from pathlib import Path

import pandas as pd

from backtest.signal import BarFrame, generate_checked

_spec = importlib.util.spec_from_file_location(
    "tsmom_btc_eth",
    Path(__file__).resolve().parents[1] / "strategies/tsmom_btc_eth.py",
)
tsmom_btc_eth = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tsmom_btc_eth)


def bars_from_close(close: dict[str, list[float]]) -> BarFrame:
    n = len(next(iter(close.values())))
    idx = pd.date_range("2021-01-01", periods=n, freq="D")  # every calendar day, not bdate_range
    mk = lambda col: pd.DataFrame({sym: v for sym, v in col.items()}, index=idx)
    return BarFrame(open=mk(close), high=mk(close), low=mk(close), close=mk(close))


def _up_then_flat(n: int, up_days: int, daily_ret: float = 0.002) -> list[float]:
    close = [100.0]
    for i in range(1, n):
        r = daily_ret if i <= up_days else 0.0
        close.append(close[-1] * (1.0 + r))
    return close


def test_defaults_are_calendar_adjusted_not_equity_defaults():
    sig = tsmom_btc_eth.Signal()
    assert (sig.lookback, sig.skip) == (365, 30)


def test_sustained_uptrend_goes_long_after_calendar_warmup():
    # 450 calendar days of steady drift: by day 395 (skip=30 + lookback=365),
    # the trailing-12-month-ending-1-month-ago return is unambiguously
    # positive -- same logic as tsmom_spy_qqq's own warm-up test, just with
    # the 365/30 calendar-day window instead of 252/21 trading-day bars.
    close = _up_then_flat(450, up_days=450, daily_ret=0.001)
    sig = tsmom_btc_eth.Signal()
    bars = bars_from_close({"BTC/USD": close})
    w = generate_checked(sig, bars)
    assert w["BTC/USD"].iloc[395] == 1.0, "first session with a full skip+lookback window"
    assert w["BTC/USD"].iloc[:395].eq(0.0).all(), "flat during the warm-up window"


def test_sustained_downtrend_stays_flat():
    close = [100.0]
    for _ in range(449):
        close.append(close[-1] * (1.0 - 0.001))
    sig = tsmom_btc_eth.Signal()
    bars = bars_from_close({"BTC/USD": close})
    w = generate_checked(sig, bars)
    assert (w["BTC/USD"] == 0.0).all(), "negative trailing momentum never goes long"


def test_two_symbols_scored_independently():
    up = _up_then_flat(450, up_days=450, daily_ret=0.001)
    down = [100.0]
    for _ in range(449):
        down.append(down[-1] * (1.0 - 0.001))
    sig = tsmom_btc_eth.Signal()
    bars = bars_from_close({"BTC/USD": up, "ETH/USD": down})
    w = generate_checked(sig, bars)
    assert w["BTC/USD"].iloc[395] == 1.0
    assert w["ETH/USD"].iloc[395] == 0.0


def test_custom_params_still_delegate_correctly():
    # A caller passing explicit params (e.g. an equity-style 252/21) should
    # still work -- proves this is a thin passthrough, not a re-implementation.
    close = _up_then_flat(300, up_days=300, daily_ret=0.001)
    sig = tsmom_btc_eth.Signal(lookback=252, skip=21)
    bars = bars_from_close({"BTC/USD": close})
    w = generate_checked(sig, bars)
    assert w["BTC/USD"].iloc[273] == 1.0
