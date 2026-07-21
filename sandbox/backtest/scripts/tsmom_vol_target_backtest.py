"""First real backtest of tsmom-vol-target (see
brain/wiki/strategies/tsmom-vol-target.md), through the real
engine.py/vectorbt path -- same convention as every prior strategy in this
vault: 2016-01-01 to 2024-12-31, folds=12, the pinned SPY/QQQ snapshot,
plus the standard OOS holdout check (oos_fraction=0.25,
reject_threshold=0.35).

Also prints, per symbol, the average position scalar during the 2020
COVID crash and 2022 bear market windows (this signal doesn't binarize,
so "flat fraction" isn't the right metric -- average scalar over the
window is), and compares turnover against tsmom-vol-accel-hysteresis's
recorded 0.992369 -- the specific thing this page exists to test.
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

COVID_CRASH = ("2020-02-19", "2020-04-07")
BEAR_2022 = ("2022-01-03", "2022-10-12")

PRIOR_TURNOVER = 0.992369  # tsmom-vol-accel-hysteresis


def main() -> None:
    repo_root = find_repo_root(Path.cwd())

    manifest = StrategyManifest.model_validate(
        {
            "schema_version": "1.0.0",
            "id": "tsmom-vol-target",
            "wiki_page": "brain/wiki/strategies/tsmom-vol-target.md",
            "market": "us_equities",
            "family": "swing",
            "universe": ["SPY", "QQQ"],
            "hypothesis": (
                "Replacing the vol-gate line's binary long/flat gate with a "
                "continuous scaling factor (min(1.0, vol_target/realized_vol), "
                "vol_target=0.15 annualized, vol_window=20) on top of tsmom-spy-qqq's "
                "unchanged signal should reduce exposure during volatility spikes "
                "with meaningfully less turnover cost than any gated variant, since "
                "there is no threshold to chatter across. Killed if Sharpe does not "
                "clear 1.0, or if turnover is not meaningfully below "
                "tsmom-vol-accel-hysteresis's 0.992369, or if COVID-window scaling "
                "provides no material de-risking versus tsmom-spy-qqq's "
                "fully-invested baseline."
            ),
            "signal_spec": {
                "language": "python",
                "entrypoint": "strategies/tsmom_vol_target.py:Signal",
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
    print(f"\nturnover: {result['metrics']['turnover']} (tsmom-vol-accel-hysteresis was {PRIOR_TURNOVER})")

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

    print("\n=== falsification check: average position scalar during known downtrends ===")
    for label, (start, end) in (("COVID crash", COVID_CRASH), ("2022 bear market", BEAR_2022)):
        window = weights.loc[start:end]
        for sym in manifest.universe:
            avg_scalar = float(window[sym].mean())
            zero_frac = float((window[sym] == 0.0).mean())
            print(
                f"{label:>16} {sym}: avg weight {avg_scalar:.3f} "
                f"(fully-flat {zero_frac:.1%} of {len(window)} sessions)"
            )


if __name__ == "__main__":
    main()
