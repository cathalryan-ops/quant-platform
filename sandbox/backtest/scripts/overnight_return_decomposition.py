"""Decomposition analysis (NOT a gated walk-forward backtest): does SPY/QQQ's
2016-2024 return accrue overnight (prior close -> today's open) or intraday
(today's open -> today's close)?

Why this is an analysis, not a Signal/manifest/run_backtest strategy: every
prior strategy in this vault expresses P&L purely through engine.py's
vbt.Portfolio.from_orders(close, ...) -- position sizing, fills, and the
returns series are ALL priced off the close series only. There is no
notion anywhere in engine.py of entering at one intra-session price (open)
and exiting at another (close) within the same session; the only timing
lever the engine has is the T -> T+1 decision shift, which is a
cross-session lag, not an intra-session split. Forcing "long overnight,
flat intraday" through Signal.generate() + run_backtest would silently
mis-price every trade (it would price the overnight leg's exit at the
NEXT close, not the next open, double-counting or dropping the intraday
leg entirely). Rather than bend the engine to fit or fudge a wrong
result through it, this computes the standard literature decomposition
directly from the pinned snapshot's own open/close columns.

Overnight return_t   = open_t / close_{t-1} - 1
Intraday return_t    = close_t / open_t - 1
Total (buy&hold)_t   = close_t / close_{t-1} - 1  (== compounding the two)

All three are reported unlevered, no fees/slippage (this is a return
ATTRIBUTION, matching the standard academic convention in the literature
this tests -- Cliff/Cooper/Gulen 2008 and Lou/Polk/Skouras 2019 both
report raw overnight-vs-intraday splits without a cost model). A separate
section quantifies why the raw overnight split is not directly tradeable
at daily granularity given this vault's standard 5bps fee + 5bps slippage
per side (see engine.py FEE_PCT/SLIPPAGE_BPS) without forcing an actual
costed backtest.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.data import bar_frame, load_snapshot  # noqa: E402
from backtest.engine import FEE_PCT, SLIPPAGE_BPS, TRADING_DAYS, find_repo_root  # noqa: E402

PINNED_HASH = "sha256:abffe4a6eae63b29c4edd312615b1b8a234d39a1ad662d3c377cd511ad687c75"
UNIVERSE = ["SPY", "QQQ"]
START, END = "2016-01-01", "2024-12-31"


def _ann_return(daily: np.ndarray) -> float:
    return float((1.0 + daily).prod() ** (TRADING_DAYS / len(daily)) - 1.0)


def _ann_vol(daily: np.ndarray) -> float:
    return float(daily.std(ddof=1) * np.sqrt(TRADING_DAYS))


def _sharpe(daily: np.ndarray) -> float:
    std = daily.std(ddof=1)
    if std == 0.0:
        return 0.0
    return float(daily.mean() / std * np.sqrt(TRADING_DAYS))


def main() -> None:
    repo_root = find_repo_root(Path.cwd())
    from backtest.data import default_snapshot_path

    snapshot_path = default_snapshot_path(repo_root / "data", UNIVERSE, START, END)
    snapshot = load_snapshot(
        snapshot_path,
        universe=UNIVERSE,
        start=START,
        end=END,
        source_feed="alpaca_iex_daily",
        expected_hash=PINNED_HASH,
        fetch=True,
    )
    bars = bar_frame(snapshot, UNIVERSE)
    open_ = bars.open
    close = bars.close

    prev_close = close.shift(1)
    overnight = (open_ / prev_close - 1.0).dropna()
    intraday = (close / open_ - 1.0).dropna()
    total = (close / prev_close - 1.0).dropna()

    print(f"Sessions: {len(total)} ({total.index[0].date()} to {total.index[-1].date()})\n")

    round_trip_cost = 2 * (FEE_PCT + SLIPPAGE_BPS / 10_000)  # in + out, one side each = fee+slip
    print(f"Reference: 5bps fee + 5bps slippage per side -> "
          f"{round_trip_cost * 1e4:.1f} bps round-trip cost per session if traded daily.\n")

    header = f"{'symbol':<6}{'leg':<12}{'ann.return':>12}{'ann.vol':>10}{'sharpe':>9}"
    print(header)
    print("-" * len(header))
    summary = {}
    for sym in UNIVERSE:
        legs = {"overnight": overnight[sym].to_numpy(), "intraday": intraday[sym].to_numpy(),
                "total (b&h)": total[sym].to_numpy()}
        summary[sym] = {}
        for name, series in legs.items():
            ar, av, sh = _ann_return(series), _ann_vol(series), _sharpe(series)
            summary[sym][name] = (ar, av, sh)
            print(f"{sym:<6}{name:<12}{ar:>11.2%}{av:>9.2%}{sh:>9.3f}")
        print()

    print("Cost-adjusted overnight feasibility (approx, subtracting round-trip "
          "bps once per session from the overnight leg's daily return):")
    for sym in UNIVERSE:
        net = overnight[sym].to_numpy() - round_trip_cost
        print(f"  {sym}: gross overnight ann.return {summary[sym]['overnight'][0]:.2%} "
              f"-> net of {round_trip_cost*1e4:.1f}bps/day "
              f"ann.return {_ann_return(net):.2%}, sharpe {_sharpe(net):.3f}")


if __name__ == "__main__":
    main()
