"""Re-arm validation suite: proves Option C's combined re-arm (see
backtest/risk.py::apply_stop_loss) is a structural improvement over the
original fresh-signal-only re-arm, isolated on the exact regime that
motivated it — ms-shift-spy-v1/QQQ's 2022-12 stop-out through the 2023
recovery it would otherwise have missed entirely (2022-10-03 -> 2023-07-03
fold).

READ-ONLY analysis: loads the pinned parquet snapshot, runs the already
fitted v1 signal + risk overlay, and only prints results. Never writes into
data/results/ms-shift-spy-v1/, data/results/ms-shift-spy-v2/, or any other
canonical result path.

Usage: sandbox/backtest/.venv/bin/python scripts/rearm_validation.py [--cooldown N]
(run from sandbox/backtest/, or anywhere with that path on sys.path)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.data import bar_frame, content_hash, load_snapshot  # noqa: E402
from backtest.risk import apply_stop_loss  # noqa: E402
from strategies.ms_shift_spy import Signal  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
RULESET_PATH = REPO_ROOT / "data/results/ms-shift-spy-v1/ruleset.json"
FOLDS = 12
LOCKOUT_FOLD_START = "2022-10-03"
LOCKOUT_FOLD_END = "2023-07-03"
OLD_STYLE_COOLDOWN = 10_000  # large enough that price-reclaim never fires


def annualized_sharpe(returns: np.ndarray) -> float:
    if len(returns) < 2 or returns.std(ddof=1) == 0.0:
        return 0.0
    return float(returns.mean() / returns.std(ddof=1) * np.sqrt(252))


def annualized_sortino(returns: np.ndarray) -> float:
    downside = np.sqrt(np.mean(np.square(np.minimum(returns, 0.0))))
    if len(returns) < 2 or downside == 0.0:
        return 0.0
    return float(returns.mean() / downside * np.sqrt(252))


def portfolio_returns(target_weights: pd.DataFrame, close: pd.DataFrame) -> pd.Series:
    """Simple daily-rebalanced equal-cash-sharing return series, matching
    engine.py's vectorbt call closely enough for comparative fold analysis
    (fees/slippage omitted here — this script is about the re-arm
    mechanism's shape, not exact recorded metrics; see engine.py for the
    officially recorded numbers)."""
    shifted_close_ret = close.pct_change().fillna(0.0)
    weighted = (target_weights.shift(0) * shifted_close_ret).mean(axis=1)
    return weighted


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cooldown", type=int, default=10, help="Option C cooldown_sessions")
    args = parser.parse_args()

    ruleset = json.loads(RULESET_PATH.read_text())
    params = ruleset["params"]
    snapshot_path = REPO_ROOT / ruleset["data_snapshot"]["parquet_path"]
    expected_hash = ruleset["data_snapshot"]["content_hash"]

    actual_hash = content_hash(snapshot_path)
    if actual_hash != expected_hash:
        print(
            f"FATAL: snapshot content hash mismatch.\n  expected: {expected_hash}\n  actual:   {actual_hash}",
            file=sys.stderr,
        )
        sys.exit(1)

    snapshot = load_snapshot(
        snapshot_path,
        universe=["SPY", "QQQ"],
        start=ruleset["data_snapshot"]["period"]["start"],
        end=ruleset["data_snapshot"]["period"]["end"],
        source_feed=ruleset["data_snapshot"]["source_feed"],
        expected_hash=expected_hash,
        fetch=False,
    )
    bars = bar_frame(snapshot, ["SPY", "QQQ"])
    close = bars.close

    signal = Signal(
        swing_lookback=params["swing_lookback"],
        atr_period=params["atr_period"],
        displacement_mult=params["displacement_mult"],
    )
    weights = signal.generate(bars)
    shifted = weights.shift(1).fillna(0.0)

    variants = {
        "1_raw_no_stop": shifted,
        "2_old_style_stop": apply_stop_loss(
            shifted, close, bars.low, stop_loss_pct=2.0, cooldown_sessions=OLD_STYLE_COOLDOWN
        ),
        f"3_option_c_cooldown_{args.cooldown}": apply_stop_loss(
            shifted, close, bars.low, stop_loss_pct=2.0, cooldown_sessions=args.cooldown
        ),
    }

    print(f"Snapshot: {snapshot_path} (hash verified)")
    print(f"Signal params: {params}\n")

    fold_mask = (close.index >= LOCKOUT_FOLD_START) & (close.index <= LOCKOUT_FOLD_END)

    header = f"{'variant':<28}{'sharpe':>10}{'sortino':>10}{'total_ret':>12}"
    print("=== Full walk-forward (12 folds, 2016-01 -> 2024-12) ===")
    print(header)
    for name, tw in variants.items():
        returns = portfolio_returns(tw, close)
        fold_sharpes = [
            annualized_sharpe(chunk) for chunk in np.array_split(returns.to_numpy(), FOLDS)
        ]
        total_ret = float((1 + returns).prod() - 1)
        print(
            f"{name:<28}{np.mean(fold_sharpes):>10.4f}"
            f"{annualized_sortino(returns.to_numpy()):>10.4f}{total_ret:>12.4%}"
        )

    print(f"\n=== Lockout fold only ({LOCKOUT_FOLD_START} -> {LOCKOUT_FOLD_END}) ===")
    print(header)
    for name, tw in variants.items():
        returns = portfolio_returns(tw, close)
        fold_returns = returns[fold_mask]
        total_ret = float((1 + fold_returns).prod() - 1)
        print(
            f"{name:<28}{annualized_sharpe(fold_returns.to_numpy()):>10.4f}"
            f"{annualized_sortino(fold_returns.to_numpy()):>10.4f}{total_ret:>12.4%}"
        )


if __name__ == "__main__":
    main()
