"""Fetch and pin a wider-universe daily-bar snapshot, expanding beyond the
existing SPY/QQQ-only pinned data (data/us_equities/daily/QQQ_SPY_*.parquet).

This does NOT replace or modify the existing SPY/QQQ snapshot or any
strategy that pins it -- those results stay reproducible exactly as
recorded. This writes a SEPARATE, additionally-pinned snapshot for future
research that needs more than two, highly-correlated large-cap index
ETFs: cross-sectional/relative-strength rotation and multi-asset trend
both need a basket to rank or diversify across, which SPY+QQQ alone can't
support (they're both broad, highly correlated US equity indices).

Universe (16 tickers), chosen for genuine dispersion, not just count:
  - Broad index breadth across market-cap tiers: SPY (large-cap blend),
    QQQ (large-cap growth), IWM (small-cap), DIA (mega-cap blue chip).
  - The 10 SPDR Select Sector ETFs with a full 2016-2024 history: XLK,
    XLF, XLE, XLV, XLI, XLY, XLP, XLU, XLB, XLRE -- enables cross-
    sectional rotation strategies (rank sectors against each other, not
    just against their own history). XLC (Communication Services) is
    deliberately EXCLUDED: it didn't launch until 2018-06-19, and since
    every downstream consumer (close_matrix/bar_frame) inner-joins on
    dates where EVERY symbol has a bar, including it would silently
    truncate everyone else's history to 2018+ as well.
  - Two non-equity diversifiers for multi-asset trend/dual-momentum
    style strategies: TLT (long-duration Treasuries), GLD (gold) -- both
    have deep history well before 2016, unlike XLC.

Run once to fetch + pin; prints the resulting path and content hash to
copy into future strategy manifests/runner scripts, same convention as
the existing SPY/QQQ snapshot's PINNED_HASH constants.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.data import (  # noqa: E402
    close_matrix,
    content_hash,
    default_snapshot_path,
    fetch_alpaca_daily,
    load_snapshot,
    write_snapshot,
)
from backtest.engine import find_repo_root  # noqa: E402
from backtest.env import load_env  # noqa: E402

load_env()

START = "2016-01-01"
END = "2024-12-31"

UNIVERSE = sorted(
    [
        # Broad index breadth
        "SPY", "QQQ", "IWM", "DIA",
        # Sector SPDRs (full 2016-2024 history; XLC excluded, launched 2018)
        "XLK", "XLF", "XLE", "XLV", "XLI", "XLY", "XLP", "XLU", "XLB", "XLRE",
        # Non-equity diversifiers
        "TLT", "GLD",
    ]
)


def main() -> None:
    repo_root = find_repo_root(Path.cwd())
    path = default_snapshot_path(repo_root / "data", UNIVERSE, START, END)

    if path.exists():
        print(f"{path} already exists -- not re-fetching (delete it first to refresh).")
    else:
        print(f"Fetching {len(UNIVERSE)} symbols from Alpaca (IEX daily bars): {UNIVERSE}")
        bars = fetch_alpaca_daily(UNIVERSE, START, END)
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
        source_feed="alpaca_iex_daily",
        fetch=False,
    )
    digest = content_hash(path)
    aligned = close_matrix(snapshot, UNIVERSE)  # inner-joined across all 16 symbols

    print(f"\ncontent_hash: {digest}")
    print(f"universe ({len(UNIVERSE)}): {UNIVERSE}")
    print(f"raw fetched range: {START} to {END}")
    print(f"aligned (all-16-present) range: {aligned.index.min().date()} to {aligned.index.max().date()}")
    print(f"aligned sessions: {len(aligned)}")

    per_symbol_first = (
        snapshot.bars.groupby("symbol")["date"].min().sort_values()
    )
    print("\nper-symbol first available date (sanity check against the aligned range above):")
    print(per_symbol_first.to_string())


if __name__ == "__main__":
    main()
