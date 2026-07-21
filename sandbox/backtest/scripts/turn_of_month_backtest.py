"""First real backtest of turn-of-month-spy-qqq (see
brain/wiki/strategies/turn-of-month-spy-qqq.md), through the real
engine.py/vectorbt path -- same convention as every prior strategy in this
vault: 2016-01-01 to 2024-12-31, folds=12, the pinned SPY/QQQ snapshot,
plus the standard OOS holdout check (oos_fraction=0.25,
reject_threshold=0.35).

Also runs the falsification check directly: average daily close-to-close
return in-window vs. out-of-window, per symbol, over the raw signal (not
the post-stop-loss engine output) -- the hypothesis specifically predicts
return concentration in the ~19% of sessions the window covers.
"""

from __future__ import annotations

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
            "id": "turn-of-month-spy-qqq",
            "wiki_page": "brain/wiki/strategies/turn-of-month-spy-qqq.md",
            "market": "us_equities",
            "family": "swing",
            "universe": ["SPY", "QQQ"],
            "hypothesis": (
                "SPY and QQQ returns are disproportionately concentrated in a "
                "window around month boundaries (last trading day of the month "
                "through the first three of the next); long-only, identical for "
                "both symbols, flat outside the window. Killed if walk-forward "
                "Sharpe does not clear 1.0, or if in-window average return is not "
                "distinguishably higher than out-of-window average return."
            ),
            "signal_spec": {
                "language": "python",
                "entrypoint": "strategies/turn_of_month_spy_qqq.py:Signal",
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
    signal = load_signal(manifest.signal_spec.entrypoint, root=Path(__file__).resolve().parents[1])
    weights = generate_checked(signal, bars)

    print("\n=== falsification check: in-window vs out-of-window average daily return ===")
    close = bars.close
    daily_ret = close.pct_change().fillna(0.0)
    in_window = weights["SPY"] == 1.0  # identical across symbols by construction
    frac_in_window = float(in_window.mean())
    print(f"sessions in window: {frac_in_window:.1%}")
    for sym in manifest.universe:
        in_ret = float(daily_ret.loc[in_window, sym].mean())
        out_ret = float(daily_ret.loc[~in_window, sym].mean())
        print(
            f"{sym}: avg daily return in-window {in_ret:.5f} "
            f"({in_ret*252:.2%} annualized), out-of-window {out_ret:.5f} "
            f"({out_ret*252:.2%} annualized)"
        )


if __name__ == "__main__":
    main()
