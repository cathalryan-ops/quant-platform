"""Unit tests for the turn-of-month calendar signal: window-edge
correctness across several month lengths, invalid params, identical
output across symbols (it's date-only), and lookahead safety through the
harness guard (should be trivial here -- there is no price dependency at
all)."""

import importlib.util
from pathlib import Path

import pandas as pd
import pytest

from backtest.signal import BarFrame, generate_checked

_spec = importlib.util.spec_from_file_location(
    "turn_of_month_spy_qqq",
    Path(__file__).resolve().parents[1] / "strategies/turn_of_month_spy_qqq.py",
)
tom = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tom)


def bars_for_dates(dates: list[str], symbols: list[str] = ["SPY"]) -> BarFrame:
    idx = pd.DatetimeIndex(dates)
    close = pd.DataFrame({sym: [100.0] * len(dates) for sym in symbols}, index=idx)
    return BarFrame(open=close, high=close, low=close, close=close)


def test_last_day_of_a_31_day_month_is_in_window():
    bars = bars_for_dates(["2024-01-31"])
    sig = tom.Signal(days_before_month_end=1, days_into_next_month=3)
    out = sig.generate(bars)
    assert out["SPY"].iloc[0] == 1.0


def test_second_to_last_day_is_out_of_window_at_default_params():
    bars = bars_for_dates(["2024-01-30"])  # 31-day month, day 30 of 31
    sig = tom.Signal(days_before_month_end=1, days_into_next_month=3)
    out = sig.generate(bars)
    assert out["SPY"].iloc[0] == 0.0


def test_last_day_of_a_28_day_month_is_in_window():
    bars = bars_for_dates(["2023-02-28"])  # non-leap Feb
    sig = tom.Signal(days_before_month_end=1, days_into_next_month=3)
    out = sig.generate(bars)
    assert out["SPY"].iloc[0] == 1.0


def test_last_day_of_a_leap_february_is_in_window():
    bars = bars_for_dates(["2024-02-29"])
    sig = tom.Signal(days_before_month_end=1, days_into_next_month=3)
    out = sig.generate(bars)
    assert out["SPY"].iloc[0] == 1.0


def test_first_three_days_of_month_in_window_fourth_is_not():
    bars = bars_for_dates(["2024-02-01", "2024-02-02", "2024-02-03", "2024-02-04"])
    sig = tom.Signal(days_before_month_end=1, days_into_next_month=3)
    out = sig.generate(bars)
    assert out["SPY"].tolist() == [1.0, 1.0, 1.0, 0.0]


def test_mid_month_is_out_of_window():
    bars = bars_for_dates(["2024-06-15"])
    sig = tom.Signal(days_before_month_end=1, days_into_next_month=3)
    out = sig.generate(bars)
    assert out["SPY"].iloc[0] == 0.0


def test_identical_weight_across_symbols():
    bars = bars_for_dates(["2024-01-31", "2024-06-15"], symbols=["SPY", "QQQ"])
    sig = tom.Signal()
    out = sig.generate(bars)
    assert out["SPY"].tolist() == out["QQQ"].tolist()


def test_invalid_params_raise():
    with pytest.raises(ValueError):
        tom.Signal(days_before_month_end=0)
    with pytest.raises(ValueError):
        tom.Signal(days_into_next_month=0)


def test_lookahead_safe_across_a_full_year():
    dates = [d.strftime("%Y-%m-%d") for d in pd.bdate_range("2016-01-01", periods=300)]
    bars = bars_for_dates(dates, symbols=["SPY", "QQQ"])
    sig = tom.Signal()
    out = generate_checked(sig, bars)  # raises LookaheadError on any leak
    assert set(pd.unique(out.to_numpy().ravel())) <= {0.0, 1.0}


def test_export_params_roundtrips_shape():
    sig = tom.Signal(days_before_month_end=1, days_into_next_month=3)
    assert sig.export_params() == {
        "type": "turn_of_month",
        "days_before_month_end": 1,
        "days_into_next_month": 3,
    }
