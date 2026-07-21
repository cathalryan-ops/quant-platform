"""Turn-of-month calendar effect on SPY/QQQ (see
brain/wiki/strategies/turn-of-month-spy-qqq.md).

Hypothesis: [[turn-of-month-effect]] -- returns cluster around month
boundaries (Ariel 1987; Lakonishok & Smidt 1988's four-day window: the
last trading day of the month plus the first three of the next). This
signal has NO price-derived logic at all -- unlike every other strategy
in this vault, it depends only on the calendar date, not on
close/high/low history at all -- a mechanism class this vault hasn't
tested yet: seasonal clustering, not trend, structure, or volatility.

Window membership is a pure per-row function of each date's own calendar
position (day-of-month vs. days-in-month), never derived from neighboring
rows in the input bars -- this is both trivially lookahead-safe (nothing
here could possibly depend on a future bar) and a deliberate
simplification: it approximates "last N TRADING days of the month" with
"last N CALENDAR days of the month", which can be off by a session or two
in months where the calendar month-end falls on a weekend. See the wiki
page for why that's an acceptable simplification for a first-pass test.
"""

from __future__ import annotations

import pandas as pd


class Signal:
    def __init__(self, days_before_month_end: int = 1, days_into_next_month: int = 3) -> None:
        if days_before_month_end < 1:
            raise ValueError("days_before_month_end must be >= 1")
        if days_into_next_month < 1:
            raise ValueError("days_into_next_month must be >= 1")
        self.days_before_month_end = days_before_month_end
        self.days_into_next_month = days_into_next_month

    def generate(self, bars) -> pd.DataFrame:
        in_window = pd.Series(
            [self._in_window(d) for d in bars.index], index=bars.index, dtype=float
        )
        return pd.DataFrame({sym: in_window for sym in bars.columns}, index=bars.index)[bars.columns]

    def _in_window(self, d: pd.Timestamp) -> float:
        near_month_end = d.day > (d.days_in_month - self.days_before_month_end)
        near_month_start = d.day <= self.days_into_next_month
        return 1.0 if (near_month_end or near_month_start) else 0.0

    def export_params(self) -> dict:
        return {
            "type": "turn_of_month",
            "days_before_month_end": self.days_before_month_end,
            "days_into_next_month": self.days_into_next_month,
        }
