"""Fetch and pin a genuinely larger cross-sectional universe: 50 single-name
US equities across all 11 GICS sectors, 2016-01-01 to 2024-12-31.

Why this exists: the existing 16-symbol snapshot
(DIA_GLD_IWM_QQQ_SPY_TLT_XLB_.../fetch_wider_universe.py) is 4 broad
index ETFs + 10 SPDR sector ETFs + TLT/GLD. Per
brain/wiki/postmortems/pinned-universe-diversity-2026-07-22.md, only
TLT/GLD are genuine diversifiers there -- the 14 equity/sector symbols
load almost entirely on one PC1 factor (71.7% of variance), because
sector ETFs are themselves aggregates that wash out real idiosyncratic
single-name dispersion. This pins 50 individual stocks -- ~4-5 per GICS
sector -- to test whether the cross-sectional-momentum mechanism
(sector_rotation.py's Signal, already proven structurally sound and
universe-agnostic) finds a materially different result on real
stock-level dispersion instead of sector-ETF aggregates.

Universe selection criteria: liquid, well-known large/mid-caps with
uninterrupted single-ticker daily history well before 2016 through 2024
(same "no truncation" requirement fetch_wider_universe.py applied to
XLC) AND no ticker-identity-breaking corporate action in the window
(merger-created replacement tickers, spinoff-driven renames). Point-in-
time GICS membership is NOT enforced -- this vault already took the same
shortcut for the 16-symbol sector snapshot ("10 of 11 current SPDR
sectors", not a historical reconstruction).

Excluded despite being obvious sector picks, and why:
  - GE (Industrials): GE HealthCare (Jan 2024) and GE Vernova (Apr 2024)
    spinoffs both fall inside the window: even though the GE ticker kept
    trading, the two distributions are large, real, one-time value
    transfers baked into raw close that would look like unexplained
    price shocks unrelated to the momentum signal. Replaced with UNP
    (Union Pacific) -- no spinoffs/renames 2016-2024.
  - LIN/DD (Materials): Praxair/Linde merger (2018, new entity trades as
    LIN, replacing PX) and the Dow/DuPont merger-then-three-way-split
    (2017-2019) both break single-ticker continuity mid-window. Used
    APD/ECL/NEM/FCX/NUE instead -- all continuously single-ticker.

Stock splits ARE present in this window for several chosen names (AAPL
4:1 Aug 2020, WMT 3:1 Feb 2024, CMCSA 2:1 Apr 2017, NEE 4:1 Oct 2020) --
handled by fetching adjustment="split" (see backtest/data.py), not by
excluding the names. Splits are a data-normalization problem, not a
universe-composition one; dividends are deliberately left unadjusted,
matching this vault's existing ETF snapshots (never dividend-adjusted).

Run once to fetch + pin; prints the resulting path, content hash, and
per-sector breakdown to copy into the strategy manifest/runner script.
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

SECTORS: dict[str, list[str]] = {
    "Information Technology": ["AAPL", "MSFT", "ORCL", "CSCO", "INTC"],
    "Health Care": ["JNJ", "PFE", "UNH", "MRK", "ABT"],
    "Financials": ["JPM", "BAC", "WFC", "GS", "AXP"],
    "Consumer Discretionary": ["HD", "MCD", "NKE", "SBUX"],
    "Communication Services": ["DIS", "CMCSA", "VZ", "T"],
    "Industrials": ["UNP", "HON", "UPS", "CAT", "BA"],
    "Consumer Staples": ["PG", "KO", "PEP", "WMT"],
    "Energy": ["XOM", "CVX", "COP", "SLB", "OXY"],
    "Utilities": ["NEE", "DUK", "SO", "D"],
    "Real Estate": ["SPG", "PLD", "PSA", "O"],
    "Materials": ["APD", "ECL", "NEM", "FCX", "NUE"],
}

UNIVERSE = sorted(sym for names in SECTORS.values() for sym in names)


def main() -> None:
    assert len(UNIVERSE) == 50, f"expected 50 symbols, got {len(UNIVERSE)}"
    repo_root = find_repo_root(Path.cwd())
    path = default_snapshot_path(repo_root / "data", UNIVERSE, START, END)

    if path.exists():
        print(f"{path} already exists -- not re-fetching (delete it first to refresh).")
    else:
        print(f"Fetching {len(UNIVERSE)} symbols from Alpaca (IEX daily bars, split-adjusted): {UNIVERSE}")
        bars = fetch_alpaca_daily(UNIVERSE, START, END, adjustment="split")
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
        source_feed="alpaca_iex_daily_split_adjusted",
        fetch=False,
    )
    digest = content_hash(path)
    aligned = close_matrix(snapshot, UNIVERSE)  # inner-joined across all 50 symbols

    print(f"\ncontent_hash: {digest}")
    print(f"universe ({len(UNIVERSE)}): {UNIVERSE}")
    print(f"raw fetched range: {START} to {END}")
    print(f"aligned (all-50-present) range: {aligned.index.min().date()} to {aligned.index.max().date()}")
    print(f"aligned sessions: {len(aligned)}")

    per_symbol_first = snapshot.bars.groupby("symbol")["date"].min().sort_values()
    print("\nper-symbol first available date (sanity check against the aligned range above):")
    print(per_symbol_first.to_string())

    print("\nsector breakdown:")
    for sector, syms in SECTORS.items():
        print(f"  {sector} ({len(syms)}): {', '.join(syms)}")


if __name__ == "__main__":
    main()
