"""First real backtest of tsmom-breadth-gate (see
brain/wiki/strategies/tsmom-breadth-gate.md), through the real
engine.py/vectorbt path. Uses the 16-symbol snapshot restricted to
SPY/QQQ (traded) plus the 10 SPDR sectors (breadth source only, always
zero weight); 2016-01-01 to 2024-12-31, folds=12, plus the standard OOS
holdout check (oos_fraction=0.25, reject_threshold=0.35).

Also runs the falsification check: how much does the gate's closed-day
set diverge from the base tsmom-spy-qqq signal's own flat days? If they're
nearly identical, breadth adds nothing beyond the base signal.
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

WIDER_UNIVERSE_HASH = "sha256:499059d460fe88bdf438ba4746151a42ba57c96fbf068ca24190174a41419bb6"
UNIVERSE = ["SPY", "QQQ", "XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY"]
TRADE_SYMBOLS = ["SPY", "QQQ"]

# tsmom-spy-qqq's recorded baseline (see brain/wiki/strategies/tsmom-spy-qqq.md).
TSMOM_BASELINE = {"sharpe": 0.813366, "sortino": 1.216489}


def main() -> None:
    repo_root = find_repo_root(Path.cwd())

    manifest = StrategyManifest.model_validate(
        {
            "schema_version": "1.0.0",
            "id": "tsmom-breadth-gate",
            "wiki_page": "brain/wiki/strategies/tsmom-breadth-gate.md",
            "market": "us_equities",
            "family": "swing",
            "universe": UNIVERSE,
            "hypothesis": (
                "tsmom-spy-qqq's unchanged signal, gated off whenever fewer than "
                "50% of the 10 SPDR sector ETFs are themselves in a positive "
                "trailing-12-1-momentum state, should filter out fragile "
                "narrow-leadership stretches and improve on tsmom-spy-qqq's "
                "0.813366 Sharpe. Killed if walk-forward Sharpe does not clear "
                "1.0 or beat the ungated baseline, or if the gate never "
                "meaningfully diverges from the base signal's own flat days."
            ),
            "signal_spec": {
                "language": "python",
                "entrypoint": "strategies/tsmom_breadth_gate.py:Signal",
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
    print(f"\ntsmom-spy-qqq baseline (recorded): {TSMOM_BASELINE}")

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
    base = signal._base.generate(bars)

    print("\n=== falsification check: does the breadth gate diverge from the base signal's own flat days? ===")
    for sym in TRADE_SYMBOLS:
        base_flat = base[sym] == 0.0
        gated_flat = weights[sym] == 0.0
        # Days the base signal was long (positive own momentum) but the
        # breadth gate forced flat anyway -- the gate binding on days the
        # base signal alone would not have gone flat.
        gate_only_flat = (~base_flat) & gated_flat
        print(
            f"{sym}: base flat {base_flat.mean():.1%} of days, "
            f"gated flat {gated_flat.mean():.1%} of days, "
            f"gate-caused-extra-flat {gate_only_flat.mean():.1%} of days "
            f"({int(gate_only_flat.sum())} sessions)"
        )


if __name__ == "__main__":
    main()
