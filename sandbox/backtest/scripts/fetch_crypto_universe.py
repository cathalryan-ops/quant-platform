"""Fetch and pin a crypto daily-bar snapshot -- the first non-us_equities
pinned data in this vault (see contracts/strategy_manifest.schema.json's
"crypto" market, added alongside this script).

13 real walk-forward backtests across structurally distinct mechanisms
(absolute momentum, structure-break, mean-reversion, cross-sectional
rotation, calendar) have converged on a Sharpe ~0.6-0.9 ceiling on the same
US-equity/sector daily universe (see
brain/wiki/postmortems/research-campaign-2026-07-21.md and
brain/wiki/postmortems/pinned-universe-diversity-2026-07-22.md). That
convergence across unrelated mechanisms looks like a property of the
data/universe, not a signal-design failure -- this pins data for a
genuinely different asset class (24/7 trading, different vol/liquidity
regime, no overnight-gap structure) to test that directly, using the same
Alpaca account and keys already in use for equities (no new credentials).

Universe (2 symbols), deliberately small and liquid, chosen to reuse
existing proven mechanisms (tsmom, ms-shift) rather than open a new sweep:
  - BTC/USD, ETH/USD -- the two most liquid USD spot pairs Alpaca offers.

Alpaca's crypto bar history starts 2021-01-01 (confirmed empirically --
requesting from 2016 returns data only from 2021-01-01 on), so this
snapshot's period is necessarily shorter than the equity snapshots'
2016-2024 window. Every day in range has a bar (no weekend/holiday gaps,
confirmed: 1461 bars/symbol for 2021-01-01..2024-12-31, exactly the
calendar-day count), unlike equities' ~252 sessions/year.

Run once to fetch + pin; prints the resulting path and content hash to
copy into the strategy manifest/runner script, same convention as
fetch_wider_universe.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.data import (  # noqa: E402
    close_matrix,
    content_hash,
    default_crypto_snapshot_path,
    fetch_alpaca_crypto_daily,
    load_snapshot,
    write_snapshot,
)
from backtest.engine import find_repo_root  # noqa: E402
from backtest.env import load_env  # noqa: E402

load_env()

START = "2021-01-01"
END = "2024-12-31"

UNIVERSE = sorted(["BTC/USD", "ETH/USD"])


def main() -> None:
    repo_root = find_repo_root(Path.cwd())
    path = default_crypto_snapshot_path(repo_root / "data", UNIVERSE, START, END)

    if path.exists():
        print(f"{path} already exists -- not re-fetching (delete it first to refresh).")
    else:
        print(f"Fetching {len(UNIVERSE)} symbols from Alpaca (crypto daily bars): {UNIVERSE}")
        bars = fetch_alpaca_crypto_daily(UNIVERSE, START, END)
        found = sorted(bars["symbol"].unique())
        missing = sorted(set(UNIVERSE) - set(found))
        if missing:
            raise RuntimeError(f"Alpaca returned no bars for: {missing}")
        write_snapshot(bars, path)
        print(f"wrote {path}")

    snapshot = load_snapshot(
        path,
        universe=UNIVERSE,
        start=START,
        end=END,
        source_feed="alpaca_crypto_daily",
        fetch=False,
    )
    digest = content_hash(path)
    aligned = close_matrix(snapshot, UNIVERSE)

    print(f"\ncontent_hash: {digest}")
    print(f"universe ({len(UNIVERSE)}): {UNIVERSE}")
    print(f"raw fetched range: {START} to {END}")
    print(f"aligned (all-present) range: {aligned.index.min().date()} to {aligned.index.max().date()}")
    print(f"aligned sessions: {len(aligned)}")

    per_symbol_first = snapshot.bars.groupby("symbol")["date"].min().sort_values()
    print("\nper-symbol first available date (sanity check against the aligned range above):")
    print(per_symbol_first.to_string())


if __name__ == "__main__":
    main()
