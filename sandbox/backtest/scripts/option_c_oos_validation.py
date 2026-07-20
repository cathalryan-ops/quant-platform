"""One-off validation run: ms-shift-spy-v1/v2 through the REAL engine.py
path (vectorbt, fees, slippage — not the simplified model used by
rearm_validation.py), comparing baseline (no cooldown, i.e. the currently
recorded behavior) against Option C (cooldown enforced), each with the new
out-of-sample holdout check (oos.py) evaluating the 2022-10 -> 2023-07
QQQ lockout regime specifically.

Cooldown is fixed at 10 sessions — the same value already used (and
committed to BEFORE this run) in rearm_validation.py. This is intentionally
NOT re-tuned here: trying several cooldown values looking for one that
clears the OOS threshold would reproduce exactly the multiple-comparisons
/ overfitting pattern already flagged in ms-shift-spy-v2's retirement note
for displacement_mult. One value, decided in advance, run once.

oos_fraction=0.25 reserves the trailing 3 of 12 walk-forward folds
(matching the already-recorded 12-fold convention) as out-of-sample —
folds 9, 10, 11 chronologically, which starts at 2022-10-03 and so
entirely covers the 2022-10 -> 2023-07 lockout fold that motivated Option C
in the first place.

Writes results to data/results/_option_c_oos_validation/ — deliberately
NOT the canonical data/results/ms-shift-spy-{v1,v2}/ paths, which remain
the retired strategies' recorded evidence. This run does not alter the
wiki's retirement status; that stays a separate, deliberate decision.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contracts import StrategyManifest  # noqa: E402

from backtest.engine import find_repo_root, run_backtest  # noqa: E402

COOLDOWN_SESSIONS = 10  # fixed in advance -- see module docstring
OOS_FRACTION = 0.25
OOS_REJECT_THRESHOLD = 0.35
FOLDS = 12

MANIFESTS = {
    "ms-shift-spy-v1": {
        "schema_version": "1.0.0",
        "id": "ms-shift-spy-v1",
        "wiki_page": "brain/wiki/strategies/ms-shift-spy.md",
        "market": "us_equities",
        "family": "ms_shift",
        "universe": ["SPY", "QQQ"],
        "hypothesis": "validation run",
        "signal_spec": {"language": "python", "entrypoint": "strategies/ms_shift_spy.py:Signal"},
        "risk": {"max_position_pct": 5.0, "stop_loss_pct": 2.0},
        "lifecycle": "retired",
        "scorecard": {
            "sharpe_wf": None, "sortino_wf": None, "max_drawdown_bt": None,
            "sharpe_paper": None, "max_drawdown_paper": None, "pnl_live": None, "rank": None,
        },
    },
    "ms-shift-spy-v2": {
        "schema_version": "1.0.0",
        "id": "ms-shift-spy-v2",
        "wiki_page": "brain/wiki/strategies/ms-shift-spy-high-displacement.md",
        "market": "us_equities",
        "family": "ms_shift",
        "universe": ["SPY", "QQQ"],
        "hypothesis": "validation run",
        "signal_spec": {
            "language": "python",
            "entrypoint": "strategies/ms_shift_spy_high_displacement.py:Signal",
        },
        "risk": {"max_position_pct": 5.0, "stop_loss_pct": 2.0},
        "lifecycle": "retired",
        "scorecard": {
            "sharpe_wf": None, "sortino_wf": None, "max_drawdown_bt": None,
            "sharpe_paper": None, "max_drawdown_paper": None, "pnl_live": None, "rank": None,
        },
    },
}

PINNED_HASH = "sha256:abffe4a6eae63b29c4edd312615b1b8a234d39a1ad662d3c377cd511ad687c75"


def run_variant(repo_root: Path, strategy_id: str, cooldown_sessions: int, label: str) -> dict:
    raw = dict(MANIFESTS[strategy_id])
    raw["risk"] = dict(raw["risk"], stop_loss_cooldown_sessions=cooldown_sessions)
    manifest = StrategyManifest.model_validate(raw)

    out_dir = repo_root / "data" / "results" / "_option_c_oos_validation" / label
    result_path = run_backtest(
        manifest,
        start="2016-01-01",
        end="2024-12-31",
        repo_root=repo_root,
        snapshot_path=repo_root / "data/us_equities/daily/QQQ_SPY_2016-01-01_2024-12-31.parquet",
        expected_hash=PINNED_HASH,
        folds=FOLDS,
        out_dir=out_dir,
        fetch=False,
        oos_fraction=OOS_FRACTION,
        oos_reject_threshold=OOS_REJECT_THRESHOLD,
    )
    return json.loads(result_path.read_text())


def main() -> None:
    repo_root = find_repo_root(Path.cwd())
    print(f"cooldown_sessions={COOLDOWN_SESSIONS} (fixed in advance, not tuned against this result)")
    print(f"oos_fraction={OOS_FRACTION} (trailing 3/{FOLDS} folds, covers the 2022-10->2023-07 lockout)")
    print(f"oos_reject_threshold={OOS_REJECT_THRESHOLD}")
    print(f"output: data/results/_option_c_oos_validation/ (NOT the canonical retired-strategy paths)\n")

    variants = (
        # 100_000 sessions >> the ~2268 trading days in this dataset, so
        # price-reclaim (condition B) never becomes eligible at all --
        # this is the TRUE original pre-Option-C behavior (fresh-signal
        # re-arm only), not "cooldown=0" (which already has Option C's
        # price-reclaim live, just with no waiting period -- a different,
        # more permissive thing from the original shipped behavior).
        (100_000, "true_original_no_price_reclaim"),
        (0, "option_c_zero_cooldown"),
        (COOLDOWN_SESSIONS, "option_c"),
    )
    for strategy_id in ("ms-shift-spy-v1", "ms-shift-spy-v2"):
        print(f"=== {strategy_id} ===")
        for cooldown, label in variants:
            result = run_variant(repo_root, strategy_id, cooldown, label)
            m = result["metrics"]
            if cooldown >= 100_000:
                tag = "TRUE ORIGINAL (fresh-signal re-arm only, no price-reclaim)"
            elif cooldown == 0:
                tag = "Option C, cooldown=0 (price-reclaim live immediately)"
            else:
                tag = f"Option C, cooldown={cooldown}"
            print(f"  {tag}:")
            print(f"    Sharpe {m['sharpe']}, Sortino {m['sortino']}, max_dd {m['max_drawdown_pct']}%")
            print(f"    passed_thresholds={result['passed_thresholds']}")
            print(f"    notes: {result['notes']}")
        print()


if __name__ == "__main__":
    main()
