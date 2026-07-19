"""P4 acceptance tests: SMA-cross manifest end-to-end, twice, byte-identical
metrics from a pinned snapshot; lookahead and hash-tamper protections."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import contracts
from backtest.data import SnapshotHashMismatch, content_hash, write_snapshot
from backtest.engine import Guardrails, ManifestRejected, run_backtest, validate_manifest
from backtest.signal import LookaheadError, generate_checked

REPO_ROOT = Path(__file__).resolve().parents[3]


def make_synthetic_snapshot(path: Path, symbols=("SPY", "QQQ")) -> None:
    """Seeded geometric random walk — deterministic across runs."""
    rng = np.random.default_rng(42)
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
    path = tmp_path / "synthetic.parquet"
    make_synthetic_snapshot(path)
    return path


@pytest.fixture()
def manifest() -> contracts.StrategyManifest:
    raw = json.loads(
        (REPO_ROOT / "contracts/examples/strategy_manifest.json").read_text()
    )
    raw["id"] = "sma-cross-test-v1"
    raw["family"] = "swing"
    raw["lifecycle"] = "backtest"
    raw["signal_spec"]["entrypoint"] = "strategies/sma_cross.py:Signal"
    return contracts.StrategyManifest.model_validate(raw)


def run(manifest, snapshot_path, out_dir, **kw):
    return run_backtest(
        manifest,
        start="2020-01-01",
        end="2023-12-29",
        repo_root=REPO_ROOT,
        snapshot_path=snapshot_path,
        out_dir=out_dir,
        fetch=False,
        source_feed="synthetic_test",
        **kw,
    )


def test_sma_cross_end_to_end_is_deterministic(manifest, snapshot_path, tmp_path):
    pinned = content_hash(snapshot_path)
    first = json.loads(
        run(manifest, snapshot_path, tmp_path / "a", expected_hash=pinned).read_text()
    )
    second = json.loads(
        run(manifest, snapshot_path, tmp_path / "b", expected_hash=pinned).read_text()
    )

    # Contract-valid, threshold-checked, snapshot-pinned...
    result = contracts.BacktestResult.model_validate(first)
    assert result.data_snapshot.content_hash == pinned
    assert isinstance(result.passed_thresholds, bool)
    assert (tmp_path / "a" / manifest.id / "backtest_equity.png").exists()

    # ...and byte-identical between runs, generated_at aside.
    for r in (first, second):
        r.pop("generated_at")
        r["equity_curve_path"] = "x"
    assert first == second


def test_tampered_snapshot_aborts(manifest, snapshot_path, tmp_path):
    pinned = content_hash(snapshot_path)
    snapshot_path.write_bytes(snapshot_path.read_bytes() + b" ")
    with pytest.raises(SnapshotHashMismatch):
        run(manifest, snapshot_path, tmp_path / "out", expected_hash=pinned)


def test_lookahead_signal_is_caught(snapshot_path):
    class CheatingSignal:
        def generate(self, close: pd.DataFrame) -> pd.DataFrame:
            # Buys today whenever TOMORROW's close is higher — the classic leak.
            return (close.shift(-1) > close).astype(float)

    idx = pd.bdate_range("2022-01-03", periods=200)
    close = pd.DataFrame(
        {"SPY": np.linspace(100, 130, 200) + np.sin(np.arange(200))}, index=idx
    )
    with pytest.raises(LookaheadError):
        generate_checked(CheatingSignal(), close)


def test_polymarket_and_guardrail_cap_rejected(manifest):
    guardrails = Guardrails.load(REPO_ROOT / "live/guardrails.toml")

    poly = manifest.model_copy(update={"market": "polymarket"})
    with pytest.raises(ManifestRejected):
        validate_manifest(poly, guardrails)

    greedy = manifest.model_copy(
        update={"risk": contracts.RiskSpec(max_position_pct=50.0, stop_loss_pct=2.0)}
    )
    with pytest.raises(ManifestRejected):
        validate_manifest(greedy, guardrails)
