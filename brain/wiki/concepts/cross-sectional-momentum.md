---
type: concept
created: 2026-07-21
---

# Cross-Sectional Momentum

Rank a basket of assets against EACH OTHER's trailing return, and rotate
into the relative leaders — as opposed to [[time-series-momentum]]'s
"absolute" construction, which judges each asset only against its own
history. The two can diverge: in a broad market downturn, a sector that
fell least still ranks at the top cross-sectionally even though its own
absolute trailing return is negative (time-series momentum would say
flat; cross-sectional says long the relative winner anyway). Widely
documented as at least as strong an anomaly as absolute momentum in the
academic literature (Jegadeesh & Titman 1993 is the canonical
cross-sectional study), and the standard construction behind sector-
rotation and relative-strength strategies.

## What matters for us

Every strategy in this vault before 2026-07-21 was single-asset: SPY and
QQQ scored independently against their own histories, because two highly
correlated large-cap index ETFs don't provide a basket to rank against.
This concept only became testable once [[volatility-targeting]]'s
retirement prompted expanding the pinned universe to 16 symbols including
10 SPDR sector ETFs (see `sandbox/backtest/DATA.md`) — [[sector-rotation]]
is the first strategy built on it. [[dual-momentum]] composes this
relative rank with time-series momentum's absolute floor, letting the
basket-relative signal go flat instead of always holding "the least bad"
candidate.

## Evidence & sources

- Jegadeesh, N. and Titman, S. (1993), "Returns to Buying Winners and
  Selling Losers: Implications for Stock Market Efficiency", *Journal of
  Finance* — the canonical cross-sectional momentum study.
- Universe expansion motivating this vault's first cross-sectional test —
  `sandbox/backtest/DATA.md`'s 16-symbol snapshot.
