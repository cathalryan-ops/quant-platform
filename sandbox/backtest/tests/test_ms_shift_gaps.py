"""Coverage-gap tests for the ms-shift-spy strategy and its manifest wiring.

Complements test_ms_shift.py (unit-level swing/displacement/lookahead) and
test_ms_shift_golden.py (Rust-fixture pin) with:
  - Signal.__init__ validation branches.
  - Degenerate inputs (flat OHLC, series shorter than atr_period) that must
    not crash and must produce all-zero weights.
  - Multi-symbol independence: one column's weights never depend on another
    column's data in the same generate() call.
  - The bearish (flatten) branch of the structure-shift gate, which the
    existing unit tests never exercise (only the bullish entry branch).
  - An ms_shift-specific end-to-end run_backtest() determinism + ruleset.json
    test, mirroring test_backtest_engine.py's sma-cross coverage.
  - A CLI-level run of `backtest.cli.main()` against an offline synthetic
    snapshot.
  - An explicit guard proving the full ms_shift backtest path never calls
    backtest.data.fetch_alpaca_daily (i.e. never touches the network or
    requires ALPACA_API_KEY / ALPACA_SECRET_KEY).

Every test in this file uses fetch=False (or a pre-written snapshot with
fetch_alpaca_daily patched to explode) — nothing here touches the network.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import contracts
import backtest.data as data_module
from backtest.cli import main as cli_main
from backtest.data import content_hash, write_snapshot
from backtest.engine import run_backtest
from backtest.signal import BarFrame

REPO_ROOT = Path(__file__).resolve().parents[3]

_spec = importlib.util.spec_from_file_location(
    "ms_shift_spy", REPO_ROOT / "sandbox/backtest/strategies/ms_shift_spy.py"
)
ms = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ms)


def bars_from_ohlc(o, h, l, c, *, columns=("SPY",)) -> BarFrame:
    """Single- or multi-symbol BarFrame; o/h/l/c are per-symbol dicts if
    columns has more than one entry, else plain lists for the one symbol."""
    n = len(c) if len(columns) == 1 else len(next(iter(c.values())))
    idx = pd.bdate_range("2020-01-01", periods=n)
    if len(columns) == 1:
        (sym,) = columns
        mk = lambda v: pd.DataFrame({sym: v}, index=idx)
        return BarFrame(open=mk(o), high=mk(h), low=mk(l), close=mk(c))
    mk = lambda d: pd.DataFrame(d, index=idx)
    return BarFrame(open=mk(o), high=mk(h), low=mk(l), close=mk(c))


# ---------------------------------------------------------------------------
# Signal.__init__ validation
# ---------------------------------------------------------------------------


def test_swing_lookback_below_one_raises():
    with pytest.raises(ValueError, match="swing_lookback"):
        ms.Signal(swing_lookback=0)


def test_atr_period_below_one_raises():
    with pytest.raises(ValueError, match="atr_period"):
        ms.Signal(atr_period=0)


@pytest.mark.parametrize("mult", [0.0, -1.0])
def test_displacement_mult_not_positive_raises(mult):
    with pytest.raises(ValueError, match="displacement_mult"):
        ms.Signal(displacement_mult=mult)


def test_boundary_valid_params_do_not_raise():
    # swing_lookback=1, atr_period=1, displacement_mult just above zero are
    # all legal (the validation is strict >=1 / >=1 / >0).
    sig = ms.Signal(swing_lookback=1, atr_period=1, displacement_mult=1e-6)
    assert sig.swing_lookback == 1
    assert sig.atr_period == 1
    assert sig.displacement_mult == 1e-6


# ---------------------------------------------------------------------------
# Degenerate inputs
# ---------------------------------------------------------------------------


def test_flat_series_never_crashes_and_is_all_zero():
    # high == low == close every bar => zero true range => ATR == 0 forever,
    # which must hit the `atr > 0.0` guard in _weights and never fire.
    n = 40
    high = [100.0] * n
    low = [100.0] * n
    close = [100.0] * n
    w = ms._weights(high, low, close, 3, 14, 1.5)
    assert w == [0.0] * n

    bars = bars_from_ohlc(close, high, low, close)
    sig = ms.Signal(swing_lookback=3, atr_period=14, displacement_mult=1.5)
    out = sig.generate(bars)
    assert (out["SPY"] == 0.0).all()


def test_series_shorter_than_atr_period_is_all_zero_no_index_error():
    # length 5 < atr_period 14: _atr_at must return None for every t, and
    # the swing-confirmation window must never index out of range either.
    high = [10.0, 11.0, 12.0, 11.0, 10.0]
    low = [9.0, 10.0, 11.0, 10.0, 9.0]
    close = [9.5, 10.5, 11.5, 10.5, 9.5]
    w = ms._weights(high, low, close, 3, 14, 1.5)
    assert w == [0.0] * 5

    bars = bars_from_ohlc(close, high, low, close)
    sig = ms.Signal(swing_lookback=3, atr_period=14, displacement_mult=1.5)
    out = sig.generate(bars)
    assert (out["SPY"] == 0.0).all()


def test_series_shorter_than_swing_window_is_all_zero_no_index_error():
    # length 3 is also shorter than 2*swing_lookback+1 (7 for k=3): the swing
    # detector's own bounds check must short-circuit rather than index OOB.
    high = [10.0, 11.0, 10.5]
    low = [9.0, 10.0, 9.5]
    close = [9.5, 10.5, 10.0]
    w = ms._weights(high, low, close, 3, 14, 1.5)
    assert w == [0.0] * 3


# ---------------------------------------------------------------------------
# Multi-symbol independence
# ---------------------------------------------------------------------------


def test_symbols_are_independent_in_multi_symbol_generate():
    k, period, mult = 2, 3, 1.5
    high_a = [10.0, 11.0, 12.0, 11.0, 10.5, 10.7, 10.9, 20.0, 20.1]
    low_a = [9.5, 10.5, 11.5, 10.5, 10.0, 10.2, 10.4, 12.0, 19.9]
    close_a = [10.0, 10.8, 11.8, 10.8, 10.2, 10.5, 10.7, 19.0, 20.0]
    # BBB: a flat, structurally unrelated series of the same length.
    high_b = [15.0] * 9
    low_b = [15.0] * 9
    close_b = [15.0] * 9

    bars = bars_from_ohlc(
        {"AAA": close_a, "BBB": close_b},
        {"AAA": high_a, "BBB": high_b},
        {"AAA": low_a, "BBB": low_b},
        {"AAA": close_a, "BBB": close_b},
        columns=("AAA", "BBB"),
    )
    sig = ms.Signal(swing_lookback=k, atr_period=period, displacement_mult=mult)
    out = sig.generate(bars)

    # AAA breaks out (matches the standalone displacement-entry scenario);
    # BBB is flat and must never fire.
    assert out["AAA"].tolist()[-2:] == [1.0, 1.0]
    assert (out["BBB"] == 0.0).all()

    # Running each symbol alone must reproduce exactly the same column —
    # i.e. no state leaks between columns inside one generate() call.
    solo_a = bars_from_ohlc(close_a, high_a, low_a, close_a, columns=("AAA",))
    solo_b = bars_from_ohlc(close_b, high_b, low_b, close_b, columns=("BBB",))
    assert sig.generate(solo_a)["AAA"].tolist() == out["AAA"].tolist()
    assert sig.generate(solo_b)["BBB"].tolist() == out["BBB"].tolist()


# ---------------------------------------------------------------------------
# Bearish (flatten) branch — the existing unit tests only ever exercise the
# bullish entry ("elif" sibling below is never hit by test_ms_shift.py).
# ---------------------------------------------------------------------------


def test_bearish_displaced_break_flattens_an_existing_long():
    k, period, mult = 2, 3, 1.5
    # Bars 0-8 reproduce the bullish entry scenario from test_ms_shift.py
    # (goes long at index 7, holds at 8). Bars 9-13 pull back, confirm a new
    # swing low at index 10 (window [8,12]), then break below it with a
    # displaced bar at index 13 — the strategy must flatten back to 0.0.
    high = [
        10.0, 11.0, 12.0, 11.0, 10.5, 10.7, 10.9, 20.0, 20.1,
        19.5, 18.0, 17.0, 17.5, 16.4,
    ]
    low = [
        9.5, 10.5, 11.5, 10.5, 10.0, 10.2, 10.4, 12.0, 19.9,
        18.5, 16.0, 16.5, 17.0, 8.0,
    ]
    close = [
        10.0, 10.8, 11.8, 10.8, 10.2, 10.5, 10.7, 19.0, 20.0,
        19.0, 16.5, 16.8, 17.2, 8.5,
    ]
    w = ms._weights(high, low, close, k, period, mult)
    assert w[7] == 1.0 and w[8] == 1.0  # long, as before
    assert w[9:13] == [1.0] * 4  # still long through the pullback
    assert w[13] == 0.0, "displaced break below the confirmed swing low must flatten"


# ---------------------------------------------------------------------------
# End-to-end run_backtest() for the ms_shift manifest, CLI, and the
# offline/no-network boundary.
# ---------------------------------------------------------------------------


def make_synthetic_snapshot(path: Path, symbols=("SPY", "QQQ")) -> None:
    """Seeded geometric random walk — deterministic across runs. Mirrors the
    helper in test_backtest_engine.py so this file stays self-contained."""
    rng = np.random.default_rng(7)
    dates = pd.bdate_range("2020-01-01", "2023-12-29").strftime("%Y-%m-%d")
    frames = []
    for i, sym in enumerate(symbols):
        rets = rng.normal(0.0004, 0.012, len(dates))
        close = 100.0 * (1 + i) * np.exp(np.cumsum(rets))
        frames.append(
            pd.DataFrame(
                {
                    "symbol": sym,
                    "date": dates,
                    "open": close * 0.999,
                    "high": close * 1.005,
                    "low": close * 0.995,
                    "close": close,
                    "volume": 1_000_000.0,
                }
            )
        )
    write_snapshot(pd.concat(frames, ignore_index=True), path)


@pytest.fixture()
def snapshot_path(tmp_path: Path) -> Path:
    path = tmp_path / "synthetic_ms_shift.parquet"
    make_synthetic_snapshot(path)
    return path


@pytest.fixture()
def ms_shift_manifest() -> contracts.StrategyManifest:
    # contracts/examples/strategy_manifest.json is already the ms-shift-spy
    # manifest (family "ms_shift", entrypoint strategies/ms_shift_spy.py);
    # just retarget id/lifecycle for test isolation.
    raw = json.loads((REPO_ROOT / "contracts/examples/strategy_manifest.json").read_text())
    assert raw["family"] == "ms_shift"
    assert raw["signal_spec"]["entrypoint"] == "strategies/ms_shift_spy.py:Signal"
    raw["id"] = "ms-shift-spy-test-v1"
    raw["lifecycle"] = "backtest"
    return contracts.StrategyManifest.model_validate(raw)


def run(manifest, snapshot_path, out_dir, **kw):
    kw.setdefault("fetch", False)
    kw.setdefault("source_feed", "synthetic_test")
    return run_backtest(
        manifest,
        start="2020-01-01",
        end="2023-12-29",
        repo_root=REPO_ROOT,
        snapshot_path=snapshot_path,
        out_dir=out_dir,
        **kw,
    )


def test_ms_shift_end_to_end_is_deterministic(ms_shift_manifest, snapshot_path, tmp_path):
    pinned = content_hash(snapshot_path)
    first = json.loads(
        run(ms_shift_manifest, snapshot_path, tmp_path / "a", expected_hash=pinned).read_text()
    )
    second = json.loads(
        run(ms_shift_manifest, snapshot_path, tmp_path / "b", expected_hash=pinned).read_text()
    )

    result = contracts.BacktestResult.model_validate(first)
    assert result.data_snapshot.content_hash == pinned
    assert isinstance(result.passed_thresholds, bool)
    assert (tmp_path / "a" / ms_shift_manifest.id / "backtest_equity.png").exists()

    for r in (first, second):
        r.pop("generated_at")
        r["equity_curve_path"] = "x"
    assert first == second


def test_ms_shift_ruleset_json_has_expected_params(ms_shift_manifest, snapshot_path, tmp_path):
    out_dir = tmp_path / "out"
    run(ms_shift_manifest, snapshot_path, out_dir)
    ruleset = json.loads((out_dir / ms_shift_manifest.id / "ruleset.json").read_text())
    assert ruleset["params"] == {
        "type": "ms_shift",
        "swing_lookback": 3,
        "atr_period": 14,
        "displacement_mult": 1.5,
    }


def test_cli_runs_ms_shift_manifest_offline(ms_shift_manifest, snapshot_path, tmp_path):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(ms_shift_manifest.model_dump_json())
    out_dir = tmp_path / "cli-out"

    exit_code = cli_main(
        [
            "--manifest",
            str(manifest_path),
            "--start",
            "2020-01-01",
            "--end",
            "2023-12-29",
            "--snapshot",
            str(snapshot_path),
            "--expected-hash",
            content_hash(snapshot_path),
            "--out",
            str(out_dir),
            "--no-fetch",
        ]
    )

    assert exit_code == 0
    result_path = out_dir / ms_shift_manifest.id / "backtest_result.json"
    assert result_path.exists()
    result = contracts.BacktestResult.model_validate_json(result_path.read_text())
    assert result.strategy_id == ms_shift_manifest.id


def test_full_ms_shift_path_never_touches_network(
    ms_shift_manifest, snapshot_path, tmp_path, monkeypatch
):
    # Snapshot already exists on disk, so run_backtest should never need to
    # fetch — even with fetch=True and no Alpaca credentials in the
    # environment. Patch fetch_alpaca_daily to blow up if it's ever called,
    # and strip the env vars, to prove the whole path is offline.
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)

    def _boom(*args, **kwargs):
        raise AssertionError("fetch_alpaca_daily must never be called by an offline test run")

    monkeypatch.setattr(data_module, "fetch_alpaca_daily", _boom)

    result_path = run(
        ms_shift_manifest, snapshot_path, tmp_path / "guard", fetch=True
    )
    result = contracts.BacktestResult.model_validate_json(result_path.read_text())
    assert result.strategy_id == ms_shift_manifest.id
