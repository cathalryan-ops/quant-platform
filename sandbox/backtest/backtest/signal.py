"""Signal protocol, entrypoint loading, and the lookahead guard.

A strategy is a class implementing `Signal`, referenced from the manifest's
signal_spec as "<file>.py:<ClassName>" relative to sandbox/backtest.

Signals receive a `BarFrame` — aligned wide OHLC matrices (index=date,
columns=symbols) — because real price-action strategies need the full bar
(swing highs/lows, high-low range), not just the close. Close-only signals
simply read `bars.close`.

Lookahead enforcement (hard rule): a correct daily signal's output for day T
depends only on bars up to T. We recompute the signal on truncated prefixes
of history at several cut points; any divergence from the full-history run
means future data leaked into the past and the run raises LookaheadError.
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

import pandas as pd


class LookaheadError(RuntimeError):
    """The signal's past output changed when future bars were removed."""


@dataclass(frozen=True)
class BarFrame:
    """Aligned wide OHLC matrices; all four share one index and columns."""

    open: pd.DataFrame
    high: pd.DataFrame
    low: pd.DataFrame
    close: pd.DataFrame

    def __len__(self) -> int:
        return len(self.close)

    @property
    def index(self) -> pd.Index:
        return self.close.index

    @property
    def columns(self) -> list[str]:
        return list(self.close.columns)

    def head(self, n: int) -> "BarFrame":
        return BarFrame(
            self.open.iloc[:n], self.high.iloc[:n], self.low.iloc[:n], self.close.iloc[:n]
        )


@runtime_checkable
class Signal(Protocol):
    def generate(self, bars: "BarFrame") -> pd.DataFrame:
        """Map OHLC bars to target long weights in [0, 1], same index/columns
        as `bars`. The weight for day T applies from the NEXT session's open
        (the engine shifts; the signal must not peek forward)."""
        ...


def load_signal(entrypoint: str, params: dict | None = None, *, root: Path) -> Signal:
    file_part, _, class_name = entrypoint.partition(":")
    if not class_name:
        raise ValueError(f"signal_spec.entrypoint must be '<file>.py:<Class>', got {entrypoint!r}")
    path = (root / file_part).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f"entrypoint {entrypoint!r} escapes {root}")
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    cls = getattr(module, class_name)
    instance = cls(**(params or {}))
    if not isinstance(instance, Signal):
        raise TypeError(f"{entrypoint} does not implement the Signal protocol")
    return instance


def generate_checked(signal: Signal, bars: BarFrame, *, n_cuts: int = 3) -> pd.DataFrame:
    """Run the signal with lookahead enforcement."""
    full = signal.generate(bars)
    if not full.index.equals(bars.index) or list(full.columns) != bars.columns:
        raise ValueError("signal output must share the input's index and columns")
    if ((full < 0) | (full > 1)).any().any():
        raise ValueError("signal weights must lie in [0, 1] (long-only v1)")

    n = len(bars)
    cuts = sorted({max(2, (i + 1) * n // (n_cuts + 1)) for i in range(n_cuts)})
    for cut in cuts:
        truncated = signal.generate(bars.head(cut))
        # The last row of the truncated run is the decision the strategy would
        # have made on that day; it must match the full-history run exactly.
        if not truncated.iloc[-1].equals(full.iloc[cut - 1]):
            raise LookaheadError(
                f"signal output for {bars.index[cut - 1].date()} changed when "
                f"bars after it were removed — future data is leaking"
            )
    return full
