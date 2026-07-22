"""First real backtest of cross-sectional-momentum-stocks50 (see
brain/wiki/strategies/cross-sectional-momentum-stocks50.md). Uses the new
50-single-name-stock snapshot (scripts/fetch_stock_universe.py);
2016-01-01 to 2024-12-31, folds=12, plus the standard OOS holdout check
(oos_fraction=0.25, reject_threshold=0.35).

Also runs the falsification check directly: does the top-15 selection
actually rotate across the ~108 monthly rebalances, or collapse onto a
persistent handful of the 50 names?
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contracts import StrategyManifest  # noqa: E402

from backtest.data import bar_frame, load_snapshot  # noqa: E402
from backtest.engine import find_repo_root, run_backtest  # noqa: E402
from backtest.signal import generate_checked, load_signal  # noqa: E402

STOCKS50_HASH = "sha256:465fbe32124a38b425744235b6eaf81087a1110f6bbfdd384253bc238c4299af"
UNIVERSE = [
    "AAPL", "ABT", "APD", "AXP", "BA", "BAC", "CAT", "CMCSA", "COP", "CSCO",
    "CVX", "D", "DIS", "DUK", "ECL", "FCX", "GS", "HD", "HON", "INTC",
    "JNJ", "JPM", "KO", "MCD", "MRK", "MSFT", "NEE", "NEM", "NKE", "NUE",
    "O", "ORCL", "OXY", "PEP", "PFE", "PG", "PLD", "PSA", "SBUX", "SLB",
    "SO", "SPG", "T", "UNH", "UNP", "UPS", "VZ", "WFC", "WMT", "XOM",
]


def main() -> None:
    repo_root = find_repo_root(Path.cwd())

    manifest = StrategyManifest.model_validate(
        {
            "schema_version": "1.0.0",
            "id": "cross-sectional-momentum-stocks50",
            "wiki_page": "brain/wiki/strategies/cross-sectional-momentum-stocks50.md",
            "market": "us_equities",
            "family": "swing",
            "universe": UNIVERSE,
            "hypothesis": (
                "Ranking 50 individual stocks (~4-5 per GICS sector) against "
                "each other's trailing 12-1 momentum each month and rotating "
                "into the top 15 (equal-weighted) tests whether real "
                "single-name idiosyncratic dispersion, unavailable in "
                "sector-rotation's 10-ETF universe, changes the "
                "cross-sectional-momentum result. Killed if walk-forward "
                "Sharpe does not clear 1.0, or if the selected set collapses "
                "onto a persistent handful of names rather than genuinely "
                "rotating."
            ),
            "signal_spec": {
                "language": "python",
                "entrypoint": "strategies/cross_sectional_momentum_stocks50.py:Signal",
            },
            "risk": {
                "max_position_pct": 5.0,
                "stop_loss_pct": 2.0,
                "stop_loss_cooldown_sessions": 10,
            },
            "lifecycle": "research",
            "scorecard": {
                "sharpe_wf": None, "sortino_wf": None, "max_drawdown_bt": None,
                "sharpe_paper": None, "max_drawdown_paper": None, "pnl_live": None, "rank": None,
            },
        }
    )

    snapshot_path = repo_root / (
        "data/us_equities/daily/"
        "AAPL_ABT_APD_AXP_BA_BAC_CAT_CMCSA_COP_CSCO_CVX_D_DIS_DUK_ECL_FCX_GS_HD_HON_INTC_"
        "JNJ_JPM_KO_MCD_MRK_MSFT_NEE_NEM_NKE_NUE_O_ORCL_OXY_PEP_PFE_PG_PLD_PSA_SBUX_SLB_"
        "SO_SPG_T_UNH_UNP_UPS_VZ_WFC_WMT_XOM_2016-01-01_2024-12-31.parquet"
    )

    result_path = run_backtest(
        manifest,
        start="2016-01-01",
        end="2024-12-31",
        repo_root=repo_root,
        snapshot_path=snapshot_path,
        expected_hash=STOCKS50_HASH,
        folds=12,
        fetch=False,
        oos_fraction=0.25,
        oos_reject_threshold=0.35,
    )
    result = json.loads(result_path.read_text())
    print(f"wrote {result_path}\n")
    print(json.dumps(result, indent=2))

    snapshot = load_snapshot(
        snapshot_path,
        universe=UNIVERSE,
        start="2016-01-01",
        end="2024-12-31",
        source_feed="alpaca_iex_daily_split_adjusted",
        expected_hash=STOCKS50_HASH,
        fetch=False,
    )
    bars = bar_frame(snapshot, UNIVERSE)
    signal = load_signal(
        manifest.signal_spec.entrypoint, root=Path(__file__).resolve().parents[1]
    )
    weights = generate_checked(signal, bars)

    print("\n=== falsification check: does the top-15 selection actually rotate? ===")
    selections: list[frozenset[str]] = []
    prev_period = None
    for date in weights.index:
        period = (date.year, date.month)
        if period != prev_period:
            selected = frozenset(weights.columns[weights.loc[date] == 1.0])
            if selected:
                selections.append(selected)
            prev_period = period

    print(f"total monthly rebalances with a non-empty selection: {len(selections)}")
    counts = Counter(sym for sel in selections for sym in sel)
    print(f"selection frequency per stock (out of {len(selections)} rebalances), most common 15:")
    for sym, n in counts.most_common(15):
        print(f"  {sym}: {n} ({n / len(selections):.1%})")
    print(f"distinct stocks selected at least once: {len(counts)} of {len(UNIVERSE)}")
    print(f"distinct 15-stock combinations used: {len(set(selections))}")


if __name__ == "__main__":
    main()
