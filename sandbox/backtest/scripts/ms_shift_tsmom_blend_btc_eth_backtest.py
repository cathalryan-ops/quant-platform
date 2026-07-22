"""First real backtest of ms-shift-tsmom-blend-btc-eth (see
brain/wiki/strategies/ms-shift-tsmom-blend-btc-eth.md), through the real
engine.py/vectorbt path. Uses the pinned BTC/USD, ETH/USD crypto snapshot
(no union-universe composition needed -- both legs already share the same
two symbols).

Runs THREE backtests under identical current-engine risk settings:
ms-shift-btc-eth alone, tsmom-btc-eth alone, and the blend -- apples-to-
apples fresh re-runs, same discipline as tsmom_ms_shift_blend_backtest.py.
Also re-confirms the correlation check already established on
ms-shift-btc-eth's own page (0.4319).
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


def _manifest(id_: str, entrypoint: str, hypothesis: str) -> StrategyManifest:
    return StrategyManifest.model_validate(
        {
            "schema_version": "1.0.0",
            "id": id_,
            "wiki_page": "brain/wiki/strategies/ms-shift-tsmom-blend-btc-eth.md",
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
            "ms-shift-btc-eth-refresh",
            "strategies/ms_shift_spy_high_displacement.py:Signal",
            "Fresh current-engine re-run of ms-shift-btc-eth for apples-to-apples comparison.",
        ),
        (
            "tsmom-btc-eth-refresh",
            "strategies/tsmom_btc_eth.py:Signal",
            "Fresh current-engine re-run of tsmom-btc-eth for apples-to-apples comparison.",
        ),
        (
            "ms-shift-tsmom-blend-btc-eth",
            "strategies/ms_shift_tsmom_blend_btc_eth.py:Signal",
            (
                "Averaging ms-shift-btc-eth's and tsmom-btc-eth's position weights 50/50 "
                "(both unchanged, blend_weight=0.5 fixed a priori). Killed if walk-forward "
                "Sharpe does not clear ms-shift-btc-eth's own current-engine Sharpe or the "
                "standing 1.0/1.2 gate."
            ),
        ),
    ]

    returns_by_leg = {}
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

    print("=== falsification check: correlation between the two legs' daily returns ===")
    a = returns_by_leg["ms-shift-btc-eth-refresh"]
    b = returns_by_leg["tsmom-btc-eth-refresh"]
    corr = float(np.corrcoef(a.to_numpy(), b.to_numpy())[0, 1])
    print(f"Pearson correlation (ms-shift-btc-eth vs tsmom-btc-eth, daily returns, full sample): {corr:.4f}")


if __name__ == "__main__":
    main()
