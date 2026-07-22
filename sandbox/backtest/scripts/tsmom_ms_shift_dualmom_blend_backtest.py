"""First real backtest of tsmom-ms-shift-dualmom-blend (see
brain/wiki/strategies/tsmom-ms-shift-dualmom-blend.md), through the real
engine.py/vectorbt path. Uses the 16-symbol wider-universe snapshot
restricted to SPY/QQQ/TLT/GLD (the union of all three legs' own
universes).

Runs FOUR backtests under identical current-engine risk settings
(stop_loss_pct=2.0, stop_loss_cooldown_sessions=10, max_position_pct=5.0):
tsmom-spy-qqq alone, ms-shift-spy-high-displacement alone,
dual-momentum-equity-bond-gold alone, and the 3-way blend -- apples-to-
apples fresh re-runs, not possibly-stale recorded scorecards, same
discipline as tsmom_ms_shift_blend_backtest.py.

Also computes the falsification check: pairwise Pearson correlation
between all three legs' daily portfolio return streams. The 2-leg blend's
own premise was "moderate not high correlation lets variance fall faster
than expected return" (confirmed at 0.5522 between tsmom and ms-shift);
the specific risk for this 3rd leg is that dual-momentum's own construction
already runs tsmom's identical lookback=252/skip=21 logic on SPY as one of
its three candidates, which could make it echo tsmom's SPY exposure
directly rather than adding a genuinely independent risk source.
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

WIDER_UNIVERSE_HASH = "sha256:499059d460fe88bdf438ba4746151a42ba57c96fbf068ca24190174a41419bb6"
FULL_UNION_UNIVERSE = ["SPY", "QQQ", "TLT", "GLD"]

RISK = {"max_position_pct": 5.0, "stop_loss_pct": 2.0, "stop_loss_cooldown_sessions": 10}


def _manifest(id_: str, universe: list[str], entrypoint: str, hypothesis: str) -> StrategyManifest:
    return StrategyManifest.model_validate(
        {
            "schema_version": "1.0.0",
            "id": id_,
            "wiki_page": "brain/wiki/strategies/tsmom-ms-shift-dualmom-blend.md",
            "market": "us_equities",
            "family": "swing",
            "universe": universe,
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
    path) so legs' raw daily returns can be correlated."""
    import vectorbt as vbt

    guardrails = Guardrails.load(repo_root / "live" / "guardrails.toml")
    snapshot = load_snapshot(
        snapshot_path,
        universe=list(manifest.universe),
        start="2016-01-01",
        end="2024-12-31",
        source_feed="alpaca_iex_daily",
        expected_hash=WIDER_UNIVERSE_HASH,
        fetch=False,
    )
    bars = bar_frame(snapshot, list(manifest.universe))
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
    snapshot_path = repo_root / (
        "data/us_equities/daily/"
        "DIA_GLD_IWM_QQQ_SPY_TLT_XLB_XLE_XLF_XLI_XLK_XLP_XLRE_XLU_XLV_XLY_2016-01-01_2024-12-31.parquet"
    )

    legs = [
        (
            "tsmom-spy-qqq-refresh",
            ["SPY", "QQQ"],
            "strategies/tsmom_spy_qqq.py:Signal",
            "Fresh current-engine re-run of tsmom-spy-qqq for apples-to-apples comparison.",
        ),
        (
            "ms-shift-spy-v2-refresh",
            ["SPY", "QQQ"],
            "strategies/ms_shift_spy_high_displacement.py:Signal",
            "Fresh current-engine re-run of ms-shift-spy-high-displacement for apples-to-apples comparison.",
        ),
        (
            "dual-momentum-refresh",
            ["SPY", "TLT", "GLD"],
            "strategies/dual_momentum_equity_bond_gold.py:Signal",
            "Fresh current-engine re-run of dual-momentum-equity-bond-gold for apples-to-apples comparison.",
        ),
        (
            "tsmom-ms-shift-dualmom-blend",
            FULL_UNION_UNIVERSE,
            "strategies/tsmom_ms_shift_dualmom_blend.py:Signal",
            (
                "Extending tsmom-ms-shift-blend (Sharpe 0.884266, this vault's best result) with a "
                "third, structurally distinct leg -- dual-momentum-equity-bond-gold, the one retired "
                "strategy with both a confirmed-real mechanism and exposure to a risk source (TLT/GLD) "
                "neither existing leg reaches. Equal 1/3 weight per leg, fixed a priori. Killed if "
                "walk-forward Sharpe does not clear the 2-leg blend's own current-engine Sharpe "
                "(re-measured fresh in this run) or the standing 1.0/1.2 gate."
            ),
        ),
    ]

    returns_by_leg = {}
    for id_, universe, entrypoint, hyp in legs:
        manifest = _manifest(id_, universe, entrypoint, hyp)
        result_path = run_backtest(
            manifest,
            start="2016-01-01",
            end="2024-12-31",
            repo_root=repo_root,
            snapshot_path=snapshot_path,
            expected_hash=WIDER_UNIVERSE_HASH,
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

    print("=== falsification check: pairwise correlation between the three legs' daily returns ===")
    pairs = [
        ("tsmom-spy-qqq-refresh", "ms-shift-spy-v2-refresh"),
        ("tsmom-spy-qqq-refresh", "dual-momentum-refresh"),
        ("ms-shift-spy-v2-refresh", "dual-momentum-refresh"),
    ]
    for x, y in pairs:
        a = returns_by_leg[x]
        b = returns_by_leg[y]
        corr = float(np.corrcoef(a.to_numpy(), b.to_numpy())[0, 1])
        print(f"Pearson correlation ({x} vs {y}, full sample): {corr:.4f}")


if __name__ == "__main__":
    main()
