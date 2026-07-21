"""First real backtest of ms-shift-spy-vol-regime (see
brain/wiki/strategies/ms-shift-spy-vol-regime.md), through the real
engine.py/vectorbt path — same convention as v1/v2: 2016-01-01 to
2024-12-31, folds=12, the pinned SPY/QQQ snapshot, plus the standard OOS
holdout check (oos_fraction=0.25, reject_threshold=0.35).

Also prints v1's canonical recorded fold Sharpes alongside this run's, per
the wiki page's falsification test: the hypothesis predicts the gate
should preserve/improve v1's three strong folds (indices 5, 6, 10 --
2019-10-2020-07, 2020-07-2021-04, 2023-07-2024-04) while filtering
exposure during the mediocre ones, not the other way around.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contracts import StrategyManifest  # noqa: E402

from backtest.engine import find_repo_root, run_backtest  # noqa: E402

PINNED_HASH = "sha256:abffe4a6eae63b29c4edd312615b1b8a234d39a1ad662d3c377cd511ad687c75"

# v1's canonical recorded fold Sharpes (data/results/ms-shift-spy-v1/backtest_result.json).
V1_FOLD_SHARPES = [-0.087, 0.471, 0.818, 0.536, 0.096, 2.086, 1.292, 0.378, 0.0, 0.613, 1.7, -0.022]
V1_STRONG_FOLDS = {5, 6, 10}  # COVID crash+recovery, 2020-21 recovery, 2023-24 AI rally


def main() -> None:
    repo_root = find_repo_root(Path.cwd())

    manifest = StrategyManifest.model_validate(
        {
            "schema_version": "1.0.0",
            "id": "ms-shift-spy-vol-regime",
            "wiki_page": "brain/wiki/strategies/ms-shift-spy-vol-regime.md",
            "market": "us_equities",
            "family": "ms_shift",
            "universe": ["SPY", "QQQ"],
            "hypothesis": (
                "ms-shift-spy's edge is conditional on the volatility regime, not only "
                "on displacement magnitude: gating v1's unchanged signal to only trade "
                "while trailing 20-day annualized realized vol is within [0.12, 0.35] "
                "will preserve or improve walk-forward Sharpe versus v1's 0.674/0.657; "
                "killed if Sharpe does not clear 1.0, or if the gate filters out v1's "
                "three strongest folds."
            ),
            "signal_spec": {
                "language": "python",
                "entrypoint": "strategies/ms_shift_vol_regime.py:Signal",
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

    result_path = run_backtest(
        manifest,
        start="2016-01-01",
        end="2024-12-31",
        repo_root=repo_root,
        snapshot_path=repo_root / "data/us_equities/daily/QQQ_SPY_2016-01-01_2024-12-31.parquet",
        expected_hash=PINNED_HASH,
        folds=12,
        fetch=False,
        oos_fraction=0.25,
        oos_reject_threshold=0.35,
    )
    result = json.loads(result_path.read_text())
    print(f"wrote {result_path}\n")
    print(json.dumps(result, indent=2))

    # Parse fold Sharpes back out of notes for the direct fold-by-fold comparison.
    notes = result["notes"]
    fold_str = notes.split("fold Sharpes ", 1)[1].split("]", 1)[0] + "]"
    this_folds = json.loads(fold_str)

    print("\n=== fold-by-fold falsification check ===")
    print(f"{'fold':>4}  {'v1 (orig)':>10}  {'vol-regime':>10}  {'v1 strong?':>10}")
    for i, (v1_s, this_s) in enumerate(zip(V1_FOLD_SHARPES, this_folds)):
        tag = "STRONG" if i in V1_STRONG_FOLDS else ""
        print(f"{i:>4}  {v1_s:>10}  {this_s:>10}  {tag:>10}")

    strong_preserved = all(this_folds[i] >= 0.5 * V1_FOLD_SHARPES[i] for i in V1_STRONG_FOLDS)
    print(f"\nstrong folds preserved (>= 50% of v1's original Sharpe each)? {strong_preserved}")


if __name__ == "__main__":
    main()
