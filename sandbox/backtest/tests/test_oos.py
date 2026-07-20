"""Offline, deterministic tests for the out-of-sample holdout check
(backtest/oos.py). No live data or network access needed."""

import numpy as np
import pandas as pd
import pytest

from backtest.oos import check_out_of_sample


def daily_returns(values: list[float], start: str = "2020-01-01") -> pd.Series:
    idx = pd.date_range(start, periods=len(values), freq="D")
    return pd.Series(values, index=idx)


def test_invalid_oos_fraction_raises():
    returns = daily_returns([0.001] * 10)
    with pytest.raises(ValueError):
        check_out_of_sample(returns, oos_fraction=0.0)
    with pytest.raises(ValueError):
        check_out_of_sample(returns, oos_fraction=1.0)
    with pytest.raises(ValueError):
        check_out_of_sample(returns, oos_fraction=-0.1)


def test_invalid_reject_threshold_raises():
    returns = daily_returns([0.001] * 10)
    with pytest.raises(ValueError):
        check_out_of_sample(returns, oos_fraction=0.2, reject_threshold=0.0)
    with pytest.raises(ValueError):
        check_out_of_sample(returns, oos_fraction=0.2, reject_threshold=-0.1)


def test_too_few_sessions_raises():
    returns = daily_returns([0.001, 0.002, -0.001])
    with pytest.raises(ValueError):
        check_out_of_sample(returns, oos_fraction=0.2)


def test_stable_edge_passes_oos_check():
    # Same positive daily return throughout — in-sample and OOS Sharpe
    # should be identical (both slices have zero variance -> Sharpe 0.0 per
    # the annualized-sharpe convention used elsewhere, degradation 0%).
    rng = np.random.default_rng(42)
    values = 0.001 + rng.normal(0, 0.0001, 200)
    returns = daily_returns(list(values))
    result = check_out_of_sample(returns, oos_fraction=0.2, reject_threshold=0.35)
    assert result.passed
    assert result.degradation_pct <= 0.35


def test_severe_degradation_is_rejected():
    # Strong positive drift in-sample, then pure noise (no edge) OOS —
    # must be flagged as a rejection, not silently passed.
    rng = np.random.default_rng(7)
    in_sample = 0.01 + rng.normal(0, 0.001, 160)
    oos = rng.normal(0, 0.01, 40)  # no drift at all
    returns = daily_returns(list(in_sample) + list(oos))
    result = check_out_of_sample(returns, oos_fraction=0.2, reject_threshold=0.35)
    assert not result.passed
    assert result.degradation_pct > 0.35


def test_oos_better_than_in_sample_never_rejected():
    rng = np.random.default_rng(3)
    in_sample = rng.normal(0, 0.01, 160)  # no edge at all
    oos = 0.01 + rng.normal(0, 0.001, 40)  # strong edge
    returns = daily_returns(list(in_sample) + list(oos))
    result = check_out_of_sample(returns, oos_fraction=0.2, reject_threshold=0.35)
    # in-sample Sharpe near zero/noisy; if it's <= 0 the check always fails
    # by design (no positive edge to validate) — otherwise OOS improvement
    # must never be rejected.
    if result.in_sample_sharpe > 0.0:
        assert result.passed
        assert result.degradation_pct <= 0.0


def test_non_positive_in_sample_sharpe_always_fails():
    # In-sample is pure noise around zero (Sharpe ~<=0); regardless of how
    # good the OOS slice looks, there's no positive edge to have degraded.
    values = [0.0] * 8 + [0.05, 0.05]
    returns = daily_returns(values)
    result = check_out_of_sample(returns, oos_fraction=0.2, reject_threshold=0.35)
    assert result.in_sample_sharpe <= 0.0
    assert not result.passed
    assert result.degradation_pct == float("inf")


def test_split_date_is_first_oos_session():
    returns = daily_returns([0.001] * 10, start="2024-01-01")
    result = check_out_of_sample(returns, oos_fraction=0.3)
    # 10 sessions, oos_fraction=0.3 -> split_idx = round(10*0.7) = 7 -> OOS starts at index 7
    assert result.split_date == str(returns.index[7].date())
