"""First real backtest of tsmom-ms-shift-blend (see
brain/wiki/strategies/tsmom-ms-shift-blend.md), through the real
engine.py/vectorbt path. Uses the original 2-symbol SPY/QQQ snapshot (no
sector data needed -- both legs already operate on SPY/QQQ only).

Runs THREE backtests under identical current-engine risk settings
(stop_loss_pct=2.0, stop_loss_cooldown_sessions=10, max_position_pct=5.0):
tsmom-spy-qqq alone, ms-shift-spy-high-displacement alone, and the blend --
so the comparison is apples-to-apples against each leg's TRUE current
number, not a possibly-stale recorded scorecard (ms-shift-spy-high-
displacement's wiki-recorded 0.813341 predates stop-loss enforcement
existing as an engine feature at all; the "Option C" investigation in its
Lifecycle history found ~0.76 with enforcement, but that number was never
written back to the canonical scorecard).

Also computes the falsification check directly: Pearson correlation
between the two legs' daily portfolio return streams. Low correlation is
the necessary condition for blending to plausibly beat either leg; a
correlation near 1.0 would mean this was never going to work regardless of
the Sharpe outcome.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contracts import StrategyManifest  # noqa: E402

from backtest.data import bar_frame, load_snapshot  # noqa: E402
from backtest.engine import FEE_PCT, SLIPPAGE_BPS, Guardrails, find_repo_root, run_backtest  # noqa: E402
from backtest.risk import apply_stop_loss  # noqa: E402
from backtest.signal import generate_checked, load_signal  # noqa: E402

PINNED_HASH = "sha256:abffe4a6eae63b29c4edd312615b1b8a234d39a1ad662d3c377cd511ad687c75"
UNIVERSE = ["SPY", "QQQ"]

RISK = {"max_position_pct": 5.0, "stop_loss_pct": 2.0, "stop_loss_cooldown_sessions": 10}


def _manifest(id_: str, entrypoint: str, hypothesis: str) -> StrategyManifest:
    return StrategyManifest.model_validate(
        {
            "schema_version": "1.0.0",
            "id": id_,
            "wiki_page": "brain/wiki/strategies/tsmom-ms-shift-blend.md",
            "market": "us_equities",
            "family": "swing",
            "universe": UNIVERSE,
            "hypothesis": hypothesis,
            "signal_spec": {"language": "python", "entrypoint": entrypoint},
            "risk": RISK,
            "lifecycle": "research",
            "scorecard": {
                "sharpe_wf": None, "sortino_wf": None, "max_drawdown_bt": None,
                "sharpe_paper": None, "max_drawdown_paper": None, "pnl_live": None, "rank": None,
            },
        }
    )


def _standalone_returns(manifest: StrategyManifest, repo_root: Path, snapshot_path: Path):
    """Replicates engine.run_backtest's return-series computation directly
    (not exposed by run_backtest's return value, which is a result-file
    path) so the two legs' raw daily returns can be correlated."""
    import vectorbt as vbt

    guardrails = Guardrails.load(repo_root / "live" / "guardrails.toml")
    snapshot = load_snapshot(
        snapshot_path,
        universe=UNIVERSE,
        start="2016-01-01",
        end="2024-12-31",
        source_feed="alpaca_iex_daily",
        expected_hash=PINNED_HASH,
        fetch=False,
    )
    bars = bar_frame(snapshot, UNIVERSE)
    signal = load_signal(manifest.signal_spec.entrypoint, root=Path(__file__).resolve().parents[1])
    weights = generate_checked(signal, bars)
    shifted = weights.shift(1).fillna(0.0)
    stopped = apply_stop_loss(
        shifted, bars.close, bars.low, manifest.risk.stop_loss_pct, manifest.risk.stop_loss_cooldown_sessions
    )
    target = (stopped * manifest.risk.max_position_pct / 100.0).astype(np.float64)
    pf = vbt.Portfolio.from_orders(
        bars.close,
        size=target,
        size_type="targetpercent",
        group_by=True,
        cash_sharing=True,
        fees=FEE_PCT,
        slippage=SLIPPAGE_BPS / 10_000,
        init_cash=guardrails.base_capital_usd,
        freq="1D",
    )
    return pf.returns()


def main() -> None:
    repo_root = find_repo_root(Path.cwd())
    snapshot_path = repo_root / "data/us_equities/daily/QQQ_SPY_2016-01-01_2024-12-31.parquet"

    legs = [
        (
            "tsmom-spy-qqq-refresh",
            "strategies/tsmom_spy_qqq.py:Signal",
            "Fresh current-engine re-run of tsmom-spy-qqq for apples-to-apples comparison.",
        ),
        (
            "ms-shift-spy-v2-refresh",
            "strategies/ms_shift_spy_high_displacement.py:Signal",
            "Fresh current-engine re-run of ms-shift-spy-high-displacement for apples-to-apples comparison.",
        ),
        (
            "tsmom-ms-shift-blend",
            "strategies/tsmom_ms_shift_blend.py:Signal",
            (
                "Averaging tsmom-spy-qqq's position weight with ms-shift-spy-high-displacement's "
                "(both unchanged, blend_weight=0.5 fixed a priori) should raise Sharpe versus either "
                "leg alone if the two signals' return streams are meaningfully uncorrelated. Killed if "
                "walk-forward Sharpe does not clear both legs' own current-engine Sharpe or the "
                "standing 1.0/1.2 gate."
            ),
        ),
    ]

    returns_by_leg = {}
    for id_, entrypoint, hyp in legs:
        manifest = _manifest(id_, entrypoint, hyp)
        result_path = run_backtest(
            manifest,
            start="2016-01-01",
            end="2024-12-31",
            repo_root=repo_root,
            snapshot_path=snapshot_path,
            expected_hash=PINNED_HASH,
            folds=12,
            fetch=False,
            oos_fraction=0.25,
            oos_reject_threshold=0.35,
        )
        result = json.loads(result_path.read_text())
        print(f"=== {id_} ===")
        print(json.dumps(result["metrics"], indent=2))
        print(f"passed_thresholds: {result['passed_thresholds']}")
        print(result["notes"])
        print()
        returns_by_leg[id_] = _standalone_returns(manifest, repo_root, snapshot_path)

    print("=== falsification check: correlation between the two legs' daily returns ===")
    a = returns_by_leg["tsmom-spy-qqq-refresh"]
    b = returns_by_leg["ms-shift-spy-v2-refresh"]
    corr = float(np.corrcoef(a.to_numpy(), b.to_numpy())[0, 1])
    print(f"Pearson correlation (tsmom-spy-qqq vs ms-shift-spy-v2 daily returns, full sample): {corr:.4f}")


if __name__ == "__main__":
    main()
