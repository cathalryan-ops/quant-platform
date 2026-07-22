"""First real backtest of tsmom-tlt-gld (see
brain/wiki/strategies/tsmom-tlt-gld.md), through the real engine.py/
vectorbt path. Uses the 16-symbol wider-universe snapshot restricted to
TLT/GLD -- tsmom_spy_qqq.py's Signal class reused completely unmodified
on a universe sharing zero symbols with tsmom-spy-qqq or
ms-shift-spy-high-displacement.

Also computes the falsification check: correlation between this
strategy's daily portfolio returns and fresh current-engine standalone
re-runs of both existing blend legs, to test directly whether a
zero-symbol-overlap third leg buys lower correlation than
dual-momentum-equity-bond-gold's shared-SPY-candidate construction did
(0.5852 vs tsmom-spy-qqq).
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
RISK = {"max_position_pct": 5.0, "stop_loss_pct": 2.0, "stop_loss_cooldown_sessions": 10}


def _manifest(id_: str, universe: list[str], entrypoint: str, hypothesis: str) -> StrategyManifest:
    return StrategyManifest.model_validate(
        {
            "schema_version": "1.0.0",
            "id": id_,
            "wiki_page": "brain/wiki/strategies/tsmom-tlt-gld.md",
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
            "tsmom-tlt-gld",
            ["TLT", "GLD"],
            "strategies/tsmom_spy_qqq.py:Signal",
            (
                "Time-series momentum (lookback=252, skip=21, unmodified) applied independently "
                "to TLT and GLD. Killed if walk-forward Sharpe does not clear the standing 1.0/1.2 "
                "gate."
            ),
        ),
        (
            "tsmom-spy-qqq-refresh",
            ["SPY", "QQQ"],
            "strategies/tsmom_spy_qqq.py:Signal",
            "Fresh current-engine re-run of tsmom-spy-qqq for correlation comparison.",
        ),
        (
            "ms-shift-spy-v2-refresh",
            ["SPY", "QQQ"],
            "strategies/ms_shift_spy_high_displacement.py:Signal",
            "Fresh current-engine re-run of ms-shift-spy-high-displacement for correlation comparison.",
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

    print("=== falsification check: correlation vs the two existing blend legs ===")
    tlt_gld = returns_by_leg["tsmom-tlt-gld"]
    for other in ("tsmom-spy-qqq-refresh", "ms-shift-spy-v2-refresh"):
        b = returns_by_leg[other]
        corr = float(np.corrcoef(tlt_gld.to_numpy(), b.to_numpy())[0, 1])
        print(f"Pearson correlation (tsmom-tlt-gld vs {other}, full sample): {corr:.4f}")

    print("\n=== per-symbol diagnostic: time-in-market ===")
    snapshot = load_snapshot(
        snapshot_path,
        universe=["TLT", "GLD"],
        start="2016-01-01",
        end="2024-12-31",
        source_feed="alpaca_iex_daily",
        expected_hash=WIDER_UNIVERSE_HASH,
        fetch=False,
    )
    bars = bar_frame(snapshot, ["TLT", "GLD"])
    signal = load_signal("strategies/tsmom_spy_qqq.py:Signal", root=Path(__file__).resolve().parents[1])
    weights = generate_checked(signal, bars)
    for sym in ["TLT", "GLD"]:
        pct_long = float((weights[sym] > 0.0).mean())
        print(f"  {sym}: {pct_long:.1%} of sessions long")


if __name__ == "__main__":
    main()
