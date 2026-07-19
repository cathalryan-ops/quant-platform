"""Snapshot layer: every backtest runs from a content-hashed parquet file.

Long format on disk: columns symbol, date, open, high, low, close, volume.
If the snapshot exists it is used as-is (reproducibility); otherwise it is
fetched from Alpaca (IEX daily bars) and written once. A run whose expected
hash no longer matches the file aborts.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

BAR_COLUMNS = ["symbol", "date", "open", "high", "low", "close", "volume"]


class SnapshotHashMismatch(RuntimeError):
    """The parquet file changed since the hash was pinned — result would not be reproducible."""


@dataclass(frozen=True)
class Snapshot:
    path: Path
    content_hash: str
    source_feed: str
    start: str
    end: str
    bars: pd.DataFrame  # long format, BAR_COLUMNS


def content_hash(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return f"sha256:{h.hexdigest()}"


def default_snapshot_path(data_dir: Path, universe: list[str], start: str, end: str) -> Path:
    name = f"{'_'.join(sorted(universe))}_{start}_{end}.parquet"
    return data_dir / "us_equities" / "daily" / name


def fetch_alpaca_daily(universe: list[str], start: str, end: str) -> pd.DataFrame:
    """Fetch daily IEX bars from Alpaca. Requires ALPACA_API_KEY / ALPACA_SECRET_KEY
    (data/paper keys only — live keys never exist in agent environments)."""
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame

    client = StockHistoricalDataClient(
        api_key=os.environ["ALPACA_API_KEY"],
        secret_key=os.environ["ALPACA_SECRET_KEY"],
    )
    req = StockBarsRequest(
        symbol_or_symbols=universe, timeframe=TimeFrame.Day, start=start, end=end
    )
    df = client.get_stock_bars(req).df.reset_index()
    df["date"] = pd.to_datetime(df["timestamp"]).dt.date.astype(str)
    return df[BAR_COLUMNS].sort_values(["symbol", "date"], ignore_index=True)


def write_snapshot(bars: pd.DataFrame, path: Path) -> None:
    if list(bars.columns) != BAR_COLUMNS:
        raise ValueError(f"snapshot must have columns {BAR_COLUMNS}, got {list(bars.columns)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    bars.sort_values(["symbol", "date"], ignore_index=True).to_parquet(path, index=False)


def load_snapshot(
    path: Path,
    *,
    universe: list[str],
    start: str,
    end: str,
    source_feed: str,
    expected_hash: str | None = None,
    fetch: bool = True,
) -> Snapshot:
    if not path.exists():
        if not fetch:
            raise FileNotFoundError(f"snapshot {path} missing and fetch disabled")
        write_snapshot(fetch_alpaca_daily(universe, start, end), path)

    digest = content_hash(path)
    if expected_hash is not None and digest != expected_hash:
        raise SnapshotHashMismatch(
            f"{path}: expected {expected_hash}, found {digest} — refusing to run"
        )

    bars = pd.read_parquet(path)
    missing = set(universe) - set(bars["symbol"].unique())
    if missing:
        raise ValueError(f"snapshot {path} lacks symbols {sorted(missing)}")
    return Snapshot(
        path=path, content_hash=digest, source_feed=source_feed, start=start, end=end, bars=bars
    )


def close_matrix(snapshot: Snapshot, universe: list[str]) -> pd.DataFrame:
    """Wide close-price matrix (index=date, columns=symbols), restricted to the period."""
    bars = snapshot.bars
    bars = bars[(bars["date"] >= snapshot.start) & (bars["date"] <= snapshot.end)]
    wide = bars.pivot(index="date", columns="symbol", values="close")[universe]
    wide.index = pd.to_datetime(wide.index)
    return wide.sort_index().dropna(how="any")
