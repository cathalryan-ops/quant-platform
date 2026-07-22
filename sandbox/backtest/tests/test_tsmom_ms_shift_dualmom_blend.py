"""Unit tests for the three-way tsmom/ms-shift/dual-momentum blend: per-leg
column routing (each leg only ever contributes to its own columns), the
blend arithmetic on the shared SPY column, weight-sum validation, output
bounds, and lookahead safety through the harness guard."""

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from backtest.signal import BarFrame, generate_checked

_spec = importlib.util.spec_from_file_location(
    "tsmom_ms_shift_dualmom_blend",
    Path(__file__).resolve().parents[1] / "strategies/tsmom_ms_shift_dualmom_blend.py",
)
blend_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(blend_mod)


def bars_from_ohlc(n: int, symbols: list[str], seed: int = 0) -> BarFrame:
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2016-01-01", periods=n)
    cols = {}
    for i, sym in enumerate(symbols):
        close = 100 * np.exp(np.cumsum(rng.normal(0.0004, 0.01, n)))
        cols[sym] = close
    close_df = pd.DataFrame(cols, index=idx)
    high = close_df * (1.0 + np.abs(rng.normal(0, 0.004, (n, len(symbols)))))
    low = close_df * (1.0 - np.abs(rng.normal(0, 0.004, (n, len(symbols)))))
    return BarFrame(open=close_df, high=high, low=low, close=close_df)


UNIVERSE = ["SPY", "QQQ", "TLT", "GLD"]


def test_qqq_column_is_pure_tsmom_plus_ms_shift_no_dual_mom_contribution():
    bars = bars_from_ohlc(400, UNIVERSE, seed=1)
    sig = blend_mod.Signal()
    out = sig.generate(bars)
    a = sig._tsmom.generate(blend_mod._subset(bars, blend_mod.TSMOM_COLS))
    b = sig._ms_shift.generate(blend_mod._subset(bars, blend_mod.MS_SHIFT_COLS))
    expected = sig.weight_tsmom * a["QQQ"] + sig.weight_ms_shift * b["QQQ"]
    assert np.allclose(out["QQQ"].to_numpy(), expected.to_numpy())


def test_tlt_and_gld_columns_are_pure_dual_momentum_no_tsmom_ms_shift_leak():
    bars = bars_from_ohlc(400, UNIVERSE, seed=2)
    sig = blend_mod.Signal()
    out = sig.generate(bars)
    c = sig._dual_mom.generate(blend_mod._subset(bars, blend_mod.DUAL_MOM_COLS))
    for col in ("TLT", "GLD"):
        expected = sig.weight_dual_mom * c[col]
        assert np.allclose(out[col].to_numpy(), expected.to_numpy())


def test_spy_column_sums_all_three_legs():
    bars = bars_from_ohlc(400, UNIVERSE, seed=3)
    sig = blend_mod.Signal()
    out = sig.generate(bars)
    a = sig._tsmom.generate(blend_mod._subset(bars, blend_mod.TSMOM_COLS))
    b = sig._ms_shift.generate(blend_mod._subset(bars, blend_mod.MS_SHIFT_COLS))
    c = sig._dual_mom.generate(blend_mod._subset(bars, blend_mod.DUAL_MOM_COLS))
    expected = (
        sig.weight_tsmom * a["SPY"] + sig.weight_ms_shift * b["SPY"] + sig.weight_dual_mom * c["SPY"]
    )
    assert np.allclose(out["SPY"].to_numpy(), expected.to_numpy())


def test_output_bounded_in_zero_one():
    bars = bars_from_ohlc(400, UNIVERSE, seed=4)
    sig = blend_mod.Signal()
    out = generate_checked(sig, bars)
    assert ((out >= 0.0) & (out <= 1.0)).to_numpy().all()


def test_weights_must_sum_to_one():
    with pytest.raises(ValueError):
        blend_mod.Signal(weight_tsmom=0.5, weight_ms_shift=0.5, weight_dual_mom=0.5)


def test_negative_weight_raises():
    with pytest.raises(ValueError):
        blend_mod.Signal(weight_tsmom=-0.1, weight_ms_shift=0.6, weight_dual_mom=0.5)


def test_lookahead_safe_on_random_close():
    bars = bars_from_ohlc(400, UNIVERSE, seed=5)
    sig = blend_mod.Signal()
    generate_checked(sig, bars)  # raises LookaheadError on any leak


def test_export_params_roundtrips_shape():
    sig = blend_mod.Signal()
    params = sig.export_params()
    assert params["type"] == "tsmom_ms_shift_dualmom_blend"
    assert params["weight_tsmom"] == pytest.approx(1.0 / 3.0)
    assert params["weight_ms_shift"] == pytest.approx(1.0 / 3.0)
    assert params["weight_dual_mom"] == pytest.approx(1.0 / 3.0)
