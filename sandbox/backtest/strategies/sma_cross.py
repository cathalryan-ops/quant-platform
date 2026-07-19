"""Trivial SMA-cross reference strategy (the P4 acceptance strategy).

Long a symbol while its fast SMA is above its slow SMA. Rolling means are
prefix-consistent, so this passes the lookahead guard by construction."""

from __future__ import annotations

import pandas as pd


class Signal:
    def __init__(self, fast: int = 20, slow: int = 50) -> None:
        if fast >= slow:
            raise ValueError("fast window must be shorter than slow window")
        self.fast = fast
        self.slow = slow

    def generate(self, close: pd.DataFrame) -> pd.DataFrame:
        fast = close.rolling(self.fast).mean()
        slow = close.rolling(self.slow).mean()
        return (fast > slow).astype(float)
