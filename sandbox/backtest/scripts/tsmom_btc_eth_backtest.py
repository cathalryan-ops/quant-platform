"""First real backtest of tsmom-btc-eth (see
brain/wiki/strategies/tsmom-btc-eth.md) -- the first non-us_equities
strategy in this vault, through the same real engine.py/vectorbt path as
every equity strategy. 2021-01-01 to 2024-12-31 (the full pinned crypto
snapshot; Alpaca's crypto bar history starts 2021-01-01), folds=8 (fixed
pre-registration choice, see the wiki page's Hypothesis section), plus the
standard OOS holdout check (oos_fraction=0.25, reject_threshold=0.35).

Also prints, per symbol, the fraction of the slow 2022 crypto bear market
and the acute November 2022 FTX-collapse shock that the strategy spent
flat -- the wiki page's pre-registered falsification test, mirroring
tsmom-spy-qqq's COVID/2022-bear check.
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

PINNED_HASH = "sha256:096c4fe845e542a6756a35c18c25903f06aadc6068464e0a68ad82a63301f355"

BEAR_2022 = ("2021-11-10", "2022-11-21")
FTX_COLLAPSE = ("2022-11-06", "2022-11-14")


def main() -> None:
    repo_root = find_repo_root(Path.cwd())

    manifest = StrategyManifest.model_validate(
        {
            "schema_version": "1.0.0",
            "id": "tsmom-btc-eth",
            "wiki_page": "brain/wiki/strategies/tsmom-btc-eth.md",
            "market": "crypto",
            "family": "swing",
            "universe": ["BTC/USD", "ETH/USD"],
            "hypothesis": (
                "BTC/USD and ETH/USD's own trailing 12-month return (skipping the "
                "most recent month, calendar-day-adjusted lookback=365/skip=30) "
                "predicts the sign of near-term drift; long-only, scored "
                "independently per symbol. Killed if walk-forward Sharpe does not "
                "clear the standing 1.0/1.2 gate, or if the strategy is long "
                "through the November 2022 FTX-collapse shock while also failing "
                "to sit out the slower 2022 bear decline."
            ),
            "signal_spec": {
                "language": "python",
                "entrypoint": "strategies/tsmom_btc_eth.py:Signal",
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

    snapshot_path = repo_root / "data/crypto/daily/BTCUSD_ETHUSD_2021-01-01_2024-12-31.parquet"

    result_path = run_backtest(
        manifest,
        start="2021-01-01",
        end="2024-12-31",
        repo_root=repo_root,
        snapshot_path=snapshot_path,
        expected_hash=PINNED_HASH,
        folds=8,
        fetch=False,
        source_feed="alpaca_crypto_daily",
        oos_fraction=0.25,
        oos_reject_threshold=0.35,
    )
    result = json.loads(result_path.read_text())
    print(f"wrote {result_path}\n")
    print(json.dumps(result, indent=2))

    snapshot = load_snapshot(
        snapshot_path,
        universe=list(manifest.universe),
        start="2021-01-01",
        end="2024-12-31",
        source_feed="alpaca_crypto_daily",
        expected_hash=PINNED_HASH,
        fetch=False,
    )
    bars = bar_frame(snapshot, list(manifest.universe))
    signal = load_signal(manifest.signal_spec.entrypoint, root=Path(__file__).resolve().parents[1])
    weights = generate_checked(signal, bars)

    print("\n=== falsification check: flat fraction during known drawdown windows ===")
    for label, (start, end) in (("2022 bear (slow)", BEAR_2022), ("FTX collapse (shock)", FTX_COLLAPSE)):
        window = weights.loc[start:end]
        for sym in manifest.universe:
            flat_frac = float((window[sym] == 0.0).mean())
            print(f"{label:>22} {sym}: flat {flat_frac:.1%} of {len(window)} sessions")


if __name__ == "__main__":
    main()
