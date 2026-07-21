"""First real backtest of dual-momentum-equity-bond-gold (see
brain/wiki/strategies/dual-momentum-equity-bond-gold.md), through the real
engine.py/vectorbt path. Uses the 16-symbol snapshot
(scripts/fetch_wider_universe.py) restricted to SPY/TLT/GLD;
2016-01-01 to 2024-12-31, folds=12, plus the standard OOS holdout check
(oos_fraction=0.25, reject_threshold=0.35).

Also runs the falsification check directly: does the strategy actually use
its absolute floor (spend real time in cash), or does it always just hold
SPY (in which case the floor is decorative and this reduces to a
concentrated equity bet)?
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
UNIVERSE = ["SPY", "TLT", "GLD"]


def main() -> None:
    repo_root = find_repo_root(Path.cwd())

    manifest = StrategyManifest.model_validate(
        {
            "schema_version": "1.0.0",
            "id": "dual-momentum-equity-bond-gold",
            "wiki_page": "brain/wiki/strategies/dual-momentum-equity-bond-gold.md",
            "market": "us_equities",
            "family": "swing",
            "universe": UNIVERSE,
            "hypothesis": (
                "Ranking SPY/TLT/GLD against each other's trailing 12-1 momentum "
                "each month and holding the relative leader -- but only if that "
                "leader's own trailing momentum is positive, else cash -- captures "
                "a flight-to-quality edge distinct from sector-rotation's "
                "always-own-something relative-strength construction. Killed if "
                "walk-forward Sharpe does not clear 1.0, or if the strategy never "
                "actually uses its cash floor (i.e. always just holds SPY)."
            ),
            "signal_spec": {
                "language": "python",
                "entrypoint": "strategies/dual_momentum_equity_bond_gold.py:Signal",
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
        universe=UNIVERSE,
        start="2016-01-01",
        end="2024-12-31",
        source_feed="alpaca_iex_daily",
        expected_hash=WIDER_UNIVERSE_HASH,
        fetch=False,
    )
    bars = bar_frame(snapshot, UNIVERSE)
    signal = load_signal(manifest.signal_spec.entrypoint, root=Path(__file__).resolve().parents[1])
    weights = generate_checked(signal, bars)

    print("\n=== falsification check: does the strategy actually use the cash floor? ===")
    selections: list[str] = []  # "CASH" or the held symbol, one per monthly rebalance
    prev_period = None
    for date in weights.index:
        period = (date.year, date.month)
        if period != prev_period:
            row = weights.loc[date]
            held = row.idxmax() if row.max() == 1.0 else "CASH"
            selections.append(held)
            prev_period = period

    print(f"total monthly rebalances (post warm-up): {len(selections)}")
    counts = Counter(selections)
    for sym, n in counts.most_common():
        print(f"  {sym}: {n} ({n / len(selections):.1%})")


if __name__ == "__main__":
    main()
