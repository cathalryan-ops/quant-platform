"""First real backtest of tsmom-vol-accel-hysteresis (see
brain/wiki/strategies/tsmom-vol-accel-hysteresis.md), through the real
engine.py/vectorbt path -- same convention as every prior strategy in this
vault: 2016-01-01 to 2024-12-31, folds=12, the pinned SPY/QQQ snapshot,
plus the standard OOS holdout check (oos_fraction=0.25,
reject_threshold=0.35).

Also runs the same falsification check as the prior two scripts (flat
fraction during the 2020 COVID crash and 2022 bear market windows),
printed directly against tsmom-vol-accel's recorded numbers -- the
specific thing this page exists to test is whether turnover drops
materially while COVID-window flat time is substantially preserved.
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

# tsmom-vol-accel's recorded numbers (see
# brain/wiki/strategies/tsmom-vol-accel.md's Evidence section).
PRIOR_TURNOVER = 1.146023
PRIOR_COVID_FLAT = {"SPY": 0.486, "QQQ": 0.457}
PRIOR_2022_FLAT = {"SPY": 0.48, "QQQ": 0.52}


def main() -> None:
    repo_root = find_repo_root(Path.cwd())

    manifest = StrategyManifest.model_validate(
        {
            "schema_version": "1.0.0",
            "id": "tsmom-vol-accel-hysteresis",
            "wiki_page": "brain/wiki/strategies/tsmom-vol-accel-hysteresis.md",
            "market": "us_equities",
            "family": "swing",
            "universe": ["SPY", "QQQ"],
            "hypothesis": (
                "tsmom-vol-accel's excess turnover comes from the single-threshold "
                "gate chattering near its own boundary. Adding a lower re-entry "
                "threshold (1.25, exit threshold unchanged at 1.75) should cut "
                "turnover materially while preserving most of the COVID-window "
                "flat-time benefit. Killed if Sharpe does not clear 1.0, or if "
                "turnover does not drop materially, or if COVID-window flat time "
                "collapses back toward 0%."
            ),
            "signal_spec": {
                "language": "python",
                "entrypoint": "strategies/tsmom_vol_accel_hysteresis.py:Signal",
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
    print(f"\nturnover: {result['metrics']['turnover']} (tsmom-vol-accel was {PRIOR_TURNOVER})")

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

    print("\n=== falsification check: flat fraction during known downtrends ===")
    print(f"{'window':>16} {'sym':>4} {'hysteresis':>12} {'vol-accel (recorded)':>22}")
    for label, (start, end), baseline in (
        ("COVID crash", COVID_CRASH, PRIOR_COVID_FLAT),
        ("2022 bear market", BEAR_2022, PRIOR_2022_FLAT),
    ):
        window = weights.loc[start:end]
        for sym in manifest.universe:
            flat_frac = float((window[sym] == 0.0).mean())
            print(f"{label:>16} {sym:>4} {flat_frac:>11.1%} {baseline[sym]:>21.1%}")


if __name__ == "__main__":
    main()
