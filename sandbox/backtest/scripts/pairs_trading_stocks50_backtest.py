"""First real backtest of pairs-trading-stocks50 (see
brain/wiki/strategies/pairs-trading-stocks50.md). Reuses the pinned
50-single-name-stock snapshot (scripts/fetch_stock_universe.py) but the
manifest's universe is the 6 symbols actually traded (JNJ/ABT, CVX/COP,
DUK/SO); 2016-01-01 to 2024-12-31, folds=12, standard OOS holdout check
(oos_fraction=0.25, reject_threshold=0.35).

Also runs the two falsification checks directly: (1) per pair, does the
spread converge (exit via |z|<=exit_z) or mostly time out (exit via
max_hold_days); (2) is each pair's cointegration stable across the first
vs. second half of the sample, or does it weaken/vanish.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contracts import StrategyManifest  # noqa: E402
from statsmodels.tsa.stattools import coint  # noqa: E402

from backtest.data import bar_frame, close_matrix, load_snapshot  # noqa: E402
from backtest.engine import find_repo_root, run_backtest  # noqa: E402
from backtest.signal import generate_checked, load_signal  # noqa: E402
from strategies.pairs_trading_stocks50 import DEFAULT_PAIRS  # noqa: E402

STOCKS50_HASH = "sha256:465fbe32124a38b425744235b6eaf81087a1110f6bbfdd384253bc238c4299af"
FULL_UNIVERSE = [
    "AAPL", "ABT", "APD", "AXP", "BA", "BAC", "CAT", "CMCSA", "COP", "CSCO",
    "CVX", "D", "DIS", "DUK", "ECL", "FCX", "GS", "HD", "HON", "INTC",
    "JNJ", "JPM", "KO", "MCD", "MRK", "MSFT", "NEE", "NEM", "NKE", "NUE",
    "O", "ORCL", "OXY", "PEP", "PFE", "PG", "PLD", "PSA", "SBUX", "SLB",
    "SO", "SPG", "T", "UNH", "UNP", "UPS", "VZ", "WFC", "WMT", "XOM",
]
TRADED_UNIVERSE = sorted({sym for pair in DEFAULT_PAIRS for sym in pair})


def main() -> None:
    repo_root = find_repo_root(Path.cwd())

    manifest = StrategyManifest.model_validate(
        {
            "schema_version": "1.0.0",
            "id": "pairs-trading-stocks50",
            "wiki_page": "brain/wiki/strategies/pairs-trading-stocks50.md",
            "market": "us_equities",
            "family": "swing",
            "universe": TRADED_UNIVERSE,
            "hypothesis": (
                "Three same-sector pairs (JNJ/ABT, CVX/COP, DUK/SO) "
                "pre-registered via Engle-Granger cointegration (p<0.05 on "
                "the full 2016-2024 sample) trade a 60-day rolling-hedge-"
                "ratio spread: long the cheap leg / short the rich leg "
                "when the spread's z-score exceeds +/-2.0, exit at "
                "|z|<=0.5 or after a 20-session safety timeout. First "
                "long-short, market-neutral mechanism in this vault -- "
                "killed if walk-forward Sharpe does not clear 1.0, or if "
                "the pairs mostly time out rather than converge, or if "
                "cointegration is unstable across the sample's two halves."
            ),
            "signal_spec": {
                "language": "python",
                "entrypoint": "strategies/pairs_trading_stocks50.py:Signal",
            },
            "risk": {
                "max_position_pct": 5.0,
                "stop_loss_pct": 4.0,
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
        "AAPL_ABT_APD_AXP_BA_BAC_CAT_CMCSA_COP_CSCO_CVX_D_DIS_DUK_ECL_FCX_GS_HD_HON_INTC_"
        "JNJ_JPM_KO_MCD_MRK_MSFT_NEE_NEM_NKE_NUE_O_ORCL_OXY_PEP_PFE_PG_PLD_PSA_SBUX_SLB_"
        "SO_SPG_T_UNH_UNP_UPS_VZ_WFC_WMT_XOM_2016-01-01_2024-12-31.parquet"
    )

    result_path = run_backtest(
        manifest,
        start="2016-01-01",
        end="2024-12-31",
        repo_root=repo_root,
        snapshot_path=snapshot_path,
        expected_hash=STOCKS50_HASH,
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
        universe=TRADED_UNIVERSE,
        start="2016-01-01",
        end="2024-12-31",
        source_feed="alpaca_iex_daily_split_adjusted",
        expected_hash=STOCKS50_HASH,
        fetch=False,
    )
    bars = bar_frame(snapshot, TRADED_UNIVERSE)
    signal = load_signal(
        manifest.signal_spec.entrypoint, root=Path(__file__).resolve().parents[1]
    )
    weights = generate_checked(signal, bars)

    print("\n=== falsification check 1: convergence vs. timeout, per pair ===")
    for sym_a, sym_b in DEFAULT_PAIRS:
        wa = weights[sym_a]
        converged = 0
        timed_out = 0
        in_trade = False
        entry_sign = 0
        hold = 0
        # Re-derive exit reason directly from the raw weight series: a
        # trade ends either by returning to 0 within max_hold_days-1
        # sessions of entry (converged) or by still being nonzero at
        # exactly max_hold_days sessions and then going flat (timeout).
        # max_hold_days is read straight from the Signal's own attribute
        # to avoid hard-coding it twice.
        max_hold = signal.max_hold_days
        for t in range(len(wa)):
            w = wa.iloc[t]
            if not in_trade:
                if w != 0.0:
                    in_trade = True
                    entry_sign = 1 if w > 0 else -1
                    hold = 1
            else:
                if w == 0.0:
                    if hold >= max_hold:
                        timed_out += 1
                    else:
                        converged += 1
                    in_trade = False
                    hold = 0
                elif (1 if w > 0 else -1) != entry_sign:
                    # sign flip without a flat day in between (shouldn't
                    # happen given the re-arm gate, but count defensively)
                    converged += 1
                    in_trade = False
                    hold = 0
                else:
                    hold += 1
        total = converged + timed_out
        pct = (converged / total * 100.0) if total else float("nan")
        print(
            f"  {sym_a}/{sym_b}: {total} completed trades, "
            f"{converged} converged ({pct:.1f}%), {timed_out} timed out"
        )

    print("\n=== falsification check 2: cointegration stability, first vs. second half ===")
    close = close_matrix(snapshot, TRADED_UNIVERSE)
    mid = len(close) // 2
    for sym_a, sym_b in DEFAULT_PAIRS:
        full_t, full_p, _ = coint(close[sym_a], close[sym_b])
        h1_t, h1_p, _ = coint(close[sym_a].iloc[:mid], close[sym_b].iloc[:mid])
        h2_t, h2_p, _ = coint(close[sym_a].iloc[mid:], close[sym_b].iloc[mid:])
        print(
            f"  {sym_a}/{sym_b}: full-sample p={full_p:.4f} | "
            f"first-half p={h1_p:.4f} | second-half p={h2_p:.4f}"
        )


if __name__ == "__main__":
    main()
