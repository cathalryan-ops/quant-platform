"""First real backtest of ms-shift-btc-eth (see
brain/wiki/strategies/ms-shift-btc-eth.md) -- the second non-us_equities
strategy in this vault, through the same real engine.py/vectorbt path.
2021-01-01 to 2024-12-31 (the full pinned crypto snapshot), folds=8 (same
as tsmom-btc-eth, for matched statistical power), plus the standard OOS
holdout check (oos_fraction=0.25, reject_threshold=0.35).

Also runs the falsification checks: (1) flat-fraction during the slow
2022 bear decline and the acute FTX-collapse shock, same windows as
tsmom-btc-eth's own check, to see whether this mechanism's
displacement-triggered entries actually react to the shock where
tsmom-btc-eth's trailing-return construction was mechanically blind to
it; (2) correlation and raw-signal agreement between this strategy and a
fresh tsmom-btc-eth re-run, to determine whether a crypto-native blend is
worth testing at all.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contracts import StrategyManifest  # noqa: E402

from backtest.data import bar_frame, load_snapshot  # noqa: E402
from backtest.engine import FEE_PCT, SLIPPAGE_BPS, Guardrails, find_repo_root, run_backtest  # noqa: E402
from backtest.risk import apply_stop_loss  # noqa: E402
from backtest.signal import generate_checked, load_signal  # noqa: E402

PINNED_HASH = "sha256:096c4fe845e542a6756a35c18c25903f06aadc6068464e0a68ad82a63301f355"
UNIVERSE = ["BTC/USD", "ETH/USD"]
RISK = {"max_position_pct": 5.0, "stop_loss_pct": 2.0, "stop_loss_cooldown_sessions": 10}

BEAR_2022 = ("2021-11-10", "2022-11-21")
FTX_COLLAPSE = ("2022-11-06", "2022-11-14")


def _manifest(id_: str, entrypoint: str, hypothesis: str) -> StrategyManifest:
    return StrategyManifest.model_validate(
        {
            "schema_version": "1.0.0",
            "id": id_,
            "wiki_page": "brain/wiki/strategies/ms-shift-btc-eth.md",
            "market": "crypto",
            "family": "ms_shift",
            "universe": UNIVERSE,
            "hypothesis": hypothesis,
            "signal_spec": {"language": "python", "entrypoint": entrypoint},
            "risk": RISK,
            "lifecycle": "research",
            "scorecard": {
                "sharpe_wf": None, "sortino_wf": None, "max_drawdown_bt": None,
                "sharpe_paper": None, "max_drawdown_paper": None, "pnl_live": None, "rank": None,
            },
        }
    )


def _standalone_returns(manifest: StrategyManifest, repo_root: Path, snapshot_path: Path):
    import vectorbt as vbt

    guardrails = Guardrails.load(repo_root / "live" / "guardrails.toml")
    snapshot = load_snapshot(
        snapshot_path,
        universe=UNIVERSE,
        start="2021-01-01",
        end="2024-12-31",
        source_feed="alpaca_crypto_daily",
        expected_hash=PINNED_HASH,
        fetch=False,
    )
    bars = bar_frame(snapshot, UNIVERSE)
    signal = load_signal(manifest.signal_spec.entrypoint, root=Path(__file__).resolve().parents[1])
    weights = generate_checked(signal, bars)
    shifted = weights.shift(1).fillna(0.0)
    stopped = apply_stop_loss(
        shifted, bars.close, bars.low, manifest.risk.stop_loss_pct, manifest.risk.stop_loss_cooldown_sessions
    )
    target = (stopped * manifest.risk.max_position_pct / 100.0).astype(np.float64)
    pf = vbt.Portfolio.from_orders(
        bars.close,
        size=target,
        size_type="targetpercent",
        group_by=True,
        cash_sharing=True,
        fees=FEE_PCT,
        slippage=SLIPPAGE_BPS / 10_000,
        init_cash=guardrails.base_capital_usd,
        freq="1D",
    )
    return pf.returns()


def main() -> None:
    repo_root = find_repo_root(Path.cwd())
    snapshot_path = repo_root / "data/crypto/daily/BTCUSD_ETHUSD_2021-01-01_2024-12-31.parquet"

    legs = [
        (
            "ms-shift-btc-eth",
            "strategies/ms_shift_spy_high_displacement.py:Signal",
            (
                "Market-structure-shift + displacement (unmodified, no calendar conversion "
                "needed) applied to BTC/USD and ETH/USD. Killed if walk-forward Sharpe does "
                "not clear the standing 1.0/1.2 gate."
            ),
        ),
        (
            "tsmom-btc-eth-refresh",
            "strategies/tsmom_btc_eth.py:Signal",
            "Fresh current-engine re-run of tsmom-btc-eth for correlation comparison.",
        ),
    ]

    returns_by_leg = {}
    weights_by_leg = {}
    for id_, entrypoint, hyp in legs:
        manifest = _manifest(id_, entrypoint, hyp)
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
        print(f"=== {id_} ===")
        print(json.dumps(result["metrics"], indent=2))
        print(f"passed_thresholds: {result['passed_thresholds']}")
        print(result["notes"])
        print()
        returns_by_leg[id_] = _standalone_returns(manifest, repo_root, snapshot_path)

        snapshot = load_snapshot(
            snapshot_path, universe=UNIVERSE, start="2021-01-01", end="2024-12-31",
            source_feed="alpaca_crypto_daily", expected_hash=PINNED_HASH, fetch=False,
        )
        bars = bar_frame(snapshot, UNIVERSE)
        signal = load_signal(manifest.signal_spec.entrypoint, root=Path(__file__).resolve().parents[1])
        weights_by_leg[id_] = generate_checked(signal, bars)

    print("=== falsification check 1: flat fraction during known drawdown windows ===")
    ms_weights = weights_by_leg["ms-shift-btc-eth"]
    for label, (start, end) in (("2022 bear (slow)", BEAR_2022), ("FTX collapse (shock)", FTX_COLLAPSE)):
        window = ms_weights.loc[start:end]
        for sym in UNIVERSE:
            flat_frac = float((window[sym] == 0.0).mean())
            print(f"{label:>22} {sym}: flat {flat_frac:.1%} of {len(window)} sessions")

    print("\n=== falsification check 2: correlation and raw-signal agreement vs tsmom-btc-eth ===")
    a = returns_by_leg["ms-shift-btc-eth"]
    b = returns_by_leg["tsmom-btc-eth-refresh"]
    corr = float(np.corrcoef(a.to_numpy(), b.to_numpy())[0, 1])
    print(f"Pearson correlation (ms-shift-btc-eth vs tsmom-btc-eth, daily returns, full sample): {corr:.4f}")

    ms_sig = weights_by_leg["ms-shift-btc-eth"]
    tsmom_sig = weights_by_leg["tsmom-btc-eth-refresh"]
    for sym in UNIVERSE:
        agree = float(((ms_sig[sym] > 0) == (tsmom_sig[sym] > 0)).mean())
        print(f"  raw signal agreement ({sym}): {agree:.1%}")


if __name__ == "__main__":
    main()
