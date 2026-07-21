"""First real backtest of 52wk-high-spy-qqq (see
brain/wiki/strategies/52wk-high-spy-qqq.md), through the real
engine.py/vectorbt path -- same convention as every prior strategy in this
vault: 2016-01-01 to 2024-12-31, folds=12, the pinned SPY/QQQ snapshot,
plus the standard OOS holdout check (oos_fraction=0.25,
reject_threshold=0.35).

Also runs the falsification check directly: raw daily-weight agreement
against tsmom_spy_qqq.Signal on the same bars -- the wiki page's point
that a high-agreement result would be a weak independent confirmation,
not two separate pieces of evidence.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contracts import StrategyManifest  # noqa: E402

from backtest.data import bar_frame, load_snapshot  # noqa: E402
from backtest.engine import find_repo_root, run_backtest  # noqa: E402
from backtest.signal import generate_checked, load_signal  # noqa: E402

PINNED_HASH = "sha256:abffe4a6eae63b29c4edd312615b1b8a234d39a1ad662d3c377cd511ad687c75"


def main() -> None:
    repo_root = find_repo_root(Path.cwd())

    manifest = StrategyManifest.model_validate(
        {
            "schema_version": "1.0.0",
            "id": "52wk-high-spy-qqq",
            "wiki_page": "brain/wiki/strategies/52wk-high-spy-qqq.md",
            "market": "us_equities",
            "family": "swing",
            "universe": ["SPY", "QQQ"],
            "hypothesis": (
                "Price proximity to its own trailing 252-session high predicts "
                "near-term continuation (George & Hwang 2004 anchoring-bias "
                "mechanism); long-only, scored independently per symbol, long "
                "while close is within 5% of the trailing high. Killed if "
                "walk-forward Sharpe does not clear 1.0."
            ),
            "signal_spec": {
                "language": "python",
                "entrypoint": "strategies/high52_spy_qqq.py:Signal",
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

    snapshot_path = repo_root / "data/us_equities/daily/QQQ_SPY_2016-01-01_2024-12-31.parquet"

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
    print(f"wrote {result_path}\n")
    print(json.dumps(result, indent=2))

    snapshot = load_snapshot(
        snapshot_path,
        universe=list(manifest.universe),
        start="2016-01-01",
        end="2024-12-31",
        source_feed="alpaca_iex_daily",
        expected_hash=PINNED_HASH,
        fetch=False,
    )
    bars = bar_frame(snapshot, list(manifest.universe))
    backtest_root = Path(__file__).resolve().parents[1]
    h52 = load_signal(manifest.signal_spec.entrypoint, root=backtest_root)
    h52_weights = generate_checked(h52, bars)

    tsmom = load_signal("strategies/tsmom_spy_qqq.py:Signal", root=backtest_root)
    tsmom_weights = generate_checked(tsmom, bars)

    print("\n=== falsification check: raw signal agreement vs tsmom-spy-qqq ===")
    for sym in manifest.universe:
        agree = float((h52_weights[sym] == tsmom_weights[sym]).mean())
        both_long = float(((h52_weights[sym] == 1.0) & (tsmom_weights[sym] == 1.0)).mean())
        print(f"{sym}: agreement {agree:.1%}, both-long {both_long:.1%} of all sessions")


if __name__ == "__main__":
    main()
