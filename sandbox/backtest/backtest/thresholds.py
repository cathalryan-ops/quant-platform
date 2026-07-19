"""Reads contracts/promotion_thresholds.toml (human-editable only — this
module only ever reads) and checks backtest metrics against [backtest_to_paper]."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BacktestThresholds:
    min_walkforward_sharpe: float
    min_walkforward_sortino: float
    max_drawdown_pct: float

    @classmethod
    def load(cls, path: Path) -> "BacktestThresholds":
        with open(path, "rb") as f:
            section = tomllib.load(f)["backtest_to_paper"]
        return cls(
            min_walkforward_sharpe=section["min_walkforward_sharpe"],
            min_walkforward_sortino=section["min_walkforward_sortino"],
            max_drawdown_pct=section["max_drawdown_pct"],
        )

    def passed(self, *, sharpe: float, sortino: float, max_drawdown_pct: float) -> bool:
        return (
            sharpe >= self.min_walkforward_sharpe
            and sortino >= self.min_walkforward_sortino
            and max_drawdown_pct <= self.max_drawdown_pct
        )
