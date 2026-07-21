"""First real backtest of sector-rotation (see
brain/wiki/strategies/sector-rotation.md), through the real
engine.py/vectorbt path. Uses the new 16-symbol snapshot
(scripts/fetch_wider_universe.py) restricted to the 10 SPDR sector ETFs;
2016-01-01 to 2024-12-31, folds=12, plus the standard OOS holdout check
(oos_fraction=0.25, reject_threshold=0.35).

Also runs the falsification check directly: does the top-3 selection
actually rotate across the ~108 monthly rebalances, or collapse onto one
or two dominant sectors?
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

WIDER_UNIVERSE_HASH = "sha256:499059d460fe88bdf438ba4746151a42ba57c96fbf068ca24190174a41419bb6"
SECTORS = ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY"]


def main() -> None:
    repo_root = find_repo_root(Path.cwd())

    manifest = StrategyManifest.model_validate(
        {
            "schema_version": "1.0.0",
            "id": "sector-rotation",
            "wiki_page": "brain/wiki/strategies/sector-rotation.md",
            "market": "us_equities",
            "family": "swing",
            "universe": SECTORS,
            "hypothesis": (
                "Ranking the 10 SPDR sector ETFs against each other's trailing "
                "12-1 momentum each month and rotating into the top 3 "
                "(equal-weighted) captures a cross-sectional edge distinct from "
                "tsmom-spy-qqq's absolute-momentum construction. Killed if "
                "walk-forward Sharpe does not clear 1.0, or if the selected set "
                "collapses onto one or two sectors rather than genuinely rotating."
            ),
            "signal_spec": {
                "language": "python",
                "entrypoint": "strategies/sector_rotation.py:Signal",
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
        "DIA_GLD_IWM_QQQ_SPY_TLT_XLB_XLE_XLF_XLI_XLK_XLP_XLRE_XLU_XLV_XLY_2016-01-01_2024-12-31.parquet"
    )

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
    print(f"wrote {result_path}\n")
    print(json.dumps(result, indent=2))

    snapshot = load_snapshot(
        snapshot_path,
        universe=SECTORS,
        start="2016-01-01",
        end="2024-12-31",
        source_feed="alpaca_iex_daily",
        expected_hash=WIDER_UNIVERSE_HASH,
        fetch=False,
    )
    bars = bar_frame(snapshot, SECTORS)
    signal = load_signal(manifest.signal_spec.entrypoint, root=Path(__file__).resolve().parents[1])
    weights = generate_checked(signal, bars)

    print("\n=== falsification check: does the top-3 selection actually rotate? ===")
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
    print("selection frequency per sector (out of rebalances above):")
    for sym, n in counts.most_common():
        print(f"  {sym}: {n} ({n / len(selections):.1%})")
    print(f"distinct 3-sector combinations used: {len(set(selections))}")


if __name__ == "__main__":
    main()
