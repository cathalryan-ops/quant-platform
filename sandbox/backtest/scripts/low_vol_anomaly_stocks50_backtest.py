"""First real backtest of low-vol-anomaly-stocks50 (see
brain/wiki/strategies/low-vol-anomaly-stocks50.md). Reuses the same
50-single-name-stock snapshot as cross-sectional-momentum-stocks50
(scripts/fetch_stock_universe.py) -- no new data fetch needed;
2016-01-01 to 2024-12-31, folds=12, plus the standard OOS holdout check
(oos_fraction=0.25, reject_threshold=0.35).

Falsification checks:
1. Composition stability -- does the least-volatile-15 selection actually
   rotate across the ~108 monthly rebalances, or collapse onto a
   persistent handful (e.g. utilities/staples dominating)?
2. Return-vs-risk decomposition -- is the low-vol basket's annualized
   return competitive with an equal-weight buy-and-hold of the full
   50-stock universe (a real anomaly: lower risk, not proportionally
   lower return), or does return drop in step with volatility (a
   risk-reduction tautology, not an anomaly)?
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contracts import StrategyManifest  # noqa: E402

from backtest.data import bar_frame, load_snapshot  # noqa: E402
from backtest.engine import find_repo_root, run_backtest  # noqa: E402
from backtest.signal import generate_checked, load_signal  # noqa: E402

STOCKS50_HASH = "sha256:465fbe32124a38b425744235b6eaf81087a1110f6bbfdd384253bc238c4299af"
UNIVERSE = [
    "AAPL", "ABT", "APD", "AXP", "BA", "BAC", "CAT", "CMCSA", "COP", "CSCO",
    "CVX", "D", "DIS", "DUK", "ECL", "FCX", "GS", "HD", "HON", "INTC",
    "JNJ", "JPM", "KO", "MCD", "MRK", "MSFT", "NEE", "NEM", "NKE", "NUE",
    "O", "ORCL", "OXY", "PEP", "PFE", "PG", "PLD", "PSA", "SBUX", "SLB",
    "SO", "SPG", "T", "UNH", "UNP", "UPS", "VZ", "WFC", "WMT", "XOM",
]
TRADING_DAYS = 252


def main() -> None:
    repo_root = find_repo_root(Path.cwd())

    manifest = StrategyManifest.model_validate(
        {
            "schema_version": "1.0.0",
            "id": "low-vol-anomaly-stocks50",
            "wiki_page": "brain/wiki/strategies/low-vol-anomaly-stocks50.md",
            "market": "us_equities",
            "family": "swing",
            "universe": UNIVERSE,
            "hypothesis": (
                "Ranking 50 individual stocks by trailing 1-year realized "
                "volatility each month and holding the 15 LEAST volatile "
                "(equal-weighted) captures the low-volatility anomaly -- a "
                "structurally different mechanism from every prior strategy "
                "in this vault (momentum, structure-break, mean-reversion, "
                "calendar). Killed if walk-forward Sharpe does not clear "
                "1.0, or if the low-vol basket's return simply scales down "
                "with its volatility (no risk-adjusted edge, a tautology "
                "not an anomaly)."
            ),
            "signal_spec": {
                "language": "python",
                "entrypoint": "strategies/low_vol_anomaly_stocks50.py:Signal",
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
        universe=UNIVERSE,
        start="2016-01-01",
        end="2024-12-31",
        source_feed="alpaca_iex_daily_split_adjusted",
        expected_hash=STOCKS50_HASH,
        fetch=False,
    )
    bars = bar_frame(snapshot, UNIVERSE)
    signal = load_signal(
        manifest.signal_spec.entrypoint, root=Path(__file__).resolve().parents[1]
    )
    weights = generate_checked(signal, bars)

    print("\n=== falsification check 1: does the low-vol-15 selection actually rotate? ===")
    selections: list[frozenset[str]] = []
    prev_period = None
    for date in weights.index:
        period = (date.year, date.month)
        if period != prev_period:
            selected = frozenset(weights.columns[weights.loc[date] == 1.0])
            if selected:
                selections.append(selected)
            prev_period = period

    print(f"total monthly rebalances with a non-empty selection: {len(selections)}")
    counts = Counter(sym for sel in selections for sym in sel)
    print(f"selection frequency per stock (out of {len(selections)} rebalances), most common 15:")
    for sym, n in counts.most_common(15):
        print(f"  {sym}: {n} ({n / len(selections):.1%})")
    print(f"distinct stocks selected at least once: {len(counts)} of {len(UNIVERSE)}")
    print(f"distinct 15-stock combinations used: {len(set(selections))}")

    print("\n=== falsification check 2: return-vs-risk decomposition vs equal-weight buy-and-hold ===")
    close = bars.close
    daily_ret = close.pct_change().dropna(how="all")
    strat_daily_ret = (weights.shift(1).fillna(0.0) * daily_ret).sum(axis=1) / weights.shift(
        1
    ).fillna(0.0).sum(axis=1).replace(0.0, np.nan)
    strat_daily_ret = strat_daily_ret.dropna()
    bench_daily_ret = daily_ret.mean(axis=1).dropna()

    def ann_stats(r: "pd.Series") -> tuple[float, float, float]:
        ann_ret = float((1.0 + r).prod() ** (TRADING_DAYS / len(r)) - 1.0)
        ann_vol = float(r.std(ddof=1) * np.sqrt(TRADING_DAYS))
        sharpe = float(r.mean() / r.std(ddof=1) * np.sqrt(TRADING_DAYS)) if r.std(ddof=1) > 0 else 0.0
        return ann_ret, ann_vol, sharpe

    strat_ret, strat_vol, strat_sharpe_raw = ann_stats(strat_daily_ret)
    bench_ret, bench_vol, bench_sharpe_raw = ann_stats(bench_daily_ret)

    print(f"low-vol-15 basket (gross, no costs): ann_return={strat_ret:.4f} ann_vol={strat_vol:.4f} raw_sharpe={strat_sharpe_raw:.4f}")
    print(f"equal-weight all-50 benchmark:        ann_return={bench_ret:.4f} ann_vol={bench_vol:.4f} raw_sharpe={bench_sharpe_raw:.4f}")
    vol_reduction = 1.0 - strat_vol / bench_vol
    ret_reduction = 1.0 - strat_ret / bench_ret if bench_ret != 0 else float("nan")
    print(f"vol reduction vs benchmark: {vol_reduction:+.1%}  |  return reduction vs benchmark: {ret_reduction:+.1%}")
    if strat_sharpe_raw > bench_sharpe_raw:
        print("-> risk-adjusted improvement: return did NOT fall proportionally to the vol cut (anomaly signature)")
    else:
        print("-> no risk-adjusted improvement: return fell as fast as (or faster than) vol (tautology signature)")


if __name__ == "__main__":
    main()
