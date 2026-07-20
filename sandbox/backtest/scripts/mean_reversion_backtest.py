"""First real backtest of mean-reversion-spy-qqq (see
brain/wiki/strategies/mean-reversion-spy-qqq.md), through the actual
engine.py/vectorbt path — same convention as ms-shift-spy: 2016-01-01 to
2024-12-31, folds=12, the pinned SPY/QQQ snapshot, plus the standard OOS
holdout check (oos_fraction=0.25, reject_threshold=0.35).

Also runs the mechanism-level falsification test promised in the wiki
page: mean forward return after a triggered entry vs. a bootstrap of
random same-length forward returns from the same series. This is
independent of the Sharpe/Sortino gate -- a Sharpe that survives on
cost/sizing mechanics alone, without a real reversion effect underneath,
shouldn't be trusted regardless of what the aggregate number says.

Writes to the strategy's own canonical data/results/mean-reversion-spy-qqq/
path -- this is the strategy's first real evidence, not a re-test of an
already-retired strategy's recorded record (unlike the earlier Option C
OOS validation, which deliberately used a separate non-canonical path).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contracts import StrategyManifest  # noqa: E402

from backtest.data import bar_frame, load_snapshot  # noqa: E402
from backtest.engine import find_repo_root, run_backtest  # noqa: E402

PINNED_HASH = "sha256:abffe4a6eae63b29c4edd312615b1b8a234d39a1ad662d3c377cd511ad687c75"
LOOKBACK, DROP_MULT, HOLD_DAYS = 20, 2.0, 5
N_BOOTSTRAP = 5000
RNG_SEED = 2026


def mechanism_falsification_check(repo_root: Path) -> dict:
    sys.path.insert(0, str(repo_root / "sandbox" / "backtest" / "strategies"))
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "mean_reversion_spy_qqq",
        repo_root / "sandbox/backtest/strategies/mean_reversion_spy_qqq.py",
    )
    mr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mr)

    snapshot = load_snapshot(
        repo_root / "data/us_equities/daily/QQQ_SPY_2016-01-01_2024-12-31.parquet",
        universe=["SPY", "QQQ"],
        start="2016-01-01",
        end="2024-12-31",
        source_feed="alpaca_iex_daily",
        expected_hash=PINNED_HASH,
        fetch=False,
    )
    bars = bar_frame(snapshot, ["SPY", "QQQ"])

    rng = np.random.default_rng(RNG_SEED)
    results = {}
    for sym in ("SPY", "QQQ"):
        close = bars.close[sym].to_numpy(dtype=float)
        n = len(close)
        weights = mr._weights(close.tolist(), LOOKBACK, DROP_MULT, HOLD_DAYS)

        trigger_idx = [
            t
            for t in range(1, n - HOLD_DAYS)
            if weights[t] == 1.0 and weights[t - 1] == 0.0
        ]
        trigger_returns = [close[t + HOLD_DAYS] / close[t] - 1.0 for t in trigger_idx]

        valid_starts = np.arange(0, n - HOLD_DAYS)
        boot_starts = rng.choice(valid_starts, size=N_BOOTSTRAP, replace=True)
        boot_returns = close[boot_starts + HOLD_DAYS] / close[boot_starts] - 1.0

        results[sym] = {
            "n_triggers": len(trigger_idx),
            "trigger_mean_fwd_return": float(np.mean(trigger_returns)) if trigger_returns else None,
            "trigger_median_fwd_return": float(np.median(trigger_returns)) if trigger_returns else None,
            "random_baseline_mean_fwd_return": float(np.mean(boot_returns)),
            "random_baseline_std_fwd_return": float(np.std(boot_returns)),
        }
    return results


def main() -> None:
    repo_root = find_repo_root(Path.cwd())

    print("=== mechanism-level falsification test ===")
    print(f"(triggered-entry forward return over {HOLD_DAYS} sessions vs. {N_BOOTSTRAP} random-start bootstrap)\n")
    mech = mechanism_falsification_check(repo_root)
    for sym, r in mech.items():
        print(f"{sym}: {r['n_triggers']} triggers")
        print(f"  trigger mean fwd return:   {r['trigger_mean_fwd_return']}")
        print(f"  trigger median fwd return: {r['trigger_median_fwd_return']}")
        print(f"  random baseline mean:      {r['random_baseline_mean_fwd_return']:.6f} (std {r['random_baseline_std_fwd_return']:.6f})")
        if r["trigger_mean_fwd_return"] is not None:
            z = (r["trigger_mean_fwd_return"] - r["random_baseline_mean_fwd_return"]) / (
                r["random_baseline_std_fwd_return"] / max(r["n_triggers"], 1) ** 0.5
            )
            print(f"  approx z-score vs random baseline: {z:.3f}")
        print()

    print("=== real engine.py walk-forward backtest ===\n")
    # Matches the manifest embedded in brain/wiki/strategies/mean-reversion-spy-qqq.md exactly.
    manifest = StrategyManifest.model_validate(
        {
            "schema_version": "1.0.0",
            "id": "mean-reversion-spy-qqq",
            "wiki_page": "brain/wiki/strategies/mean-reversion-spy-qqq.md",
            "market": "us_equities",
            "family": "swing",
            "universe": ["SPY", "QQQ"],
            "hypothesis": (
                "A close-to-close daily return >= 2.0 standard deviations below the "
                "trailing 20-day mean is followed by reversion over the next 5 sessions "
                "often enough to clear costs; killed if walk-forward Sharpe 2016-2024 < 1.0 "
                "after 5 bps fees + 5 bps slippage (same gate as ms-shift-spy), or if the "
                "mechanism-level forward-return falsification test shows no real reversion effect."
            ),
            "signal_spec": {
                "language": "python",
                "entrypoint": "strategies/mean_reversion_spy_qqq.py:Signal",
            },
            "risk": {"max_position_pct": 5.0, "stop_loss_pct": 2.0},
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


if __name__ == "__main__":
    main()
