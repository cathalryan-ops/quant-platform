---
type: concept
created: 2026-07-22
---

# Overnight return effect

A large, disproportionate share of a US equity index's long-run return
accrues **overnight** (prior session's close to the next session's open),
not during the regular trading session (open to close) — documented in
Cliff/Cooper/Gulen (2008) and refined by Lou/Polk/Skouras (2019, "A Tug
of War") as a persistent split between an overnight-favoring component
(attributed to index-fund/ETF flow timing, overnight information
processing, and differential retail-vs-institutional order-flow
patterns) and a comparatively weaker or even negative intraday
component.

## What matters for us

Structurally distinct from every other mechanism in this vault: not
[[time-series-momentum]] (no trailing-return predictor), not
[[market-structure-shift]] (no discrete displacement event), not
[[cross-sectional-momentum]]/[[low-volatility-anomaly]] (no cross-asset
ranking) — this is a **return-decomposition** claim about *when* within
a session an asset's drift accrues, requiring open AND close prices
rather than close-only.

This vault's `engine.py` cannot express "long overnight, flat/short
intraday" as a `Signal`/`run_backtest` strategy: every existing
strategy's P&L is priced entirely off `vbt.Portfolio.from_orders(close,
...)` — the only timing lever the engine has is the cross-session T→T+1
decision shift, not an intra-session open-vs-close split. Rather than
force a wrong result through the engine, `overnight-return-2026-07-22`
computed the standard decomposition directly from the pinned SPY/QQQ
snapshot's own open/close columns (see postmortem below).

**Finding**: the effect replicates directionally in this vault's own
2016-2024 SPY/QQQ sample — overnight Sharpe clears intraday Sharpe on
both symbols (SPY 0.675 vs 0.440; QQQ 0.842 vs 0.485) — but the average
daily overnight edge (a few bps/day) is smaller than this vault's
standard 20bps/day round-trip cost (5bps fee + 5bps slippage, each way),
so it is not tradeable at daily granularity under this vault's cost
model even though the underlying return-timing asymmetry is real. This
is a tradeability/cost-structure finding, not a falsification of the
effect itself.

## Evidence & sources

- Overnight/intraday Sharpe split, SPY/QQQ 2016-2024 —
  `sandbox/backtest/scripts/overnight_return_decomposition.py`, see
  [[overnight-return-2026-07-22]].
- Cliff/Cooper/Gulen (2008); Lou/Polk/Skouras (2019, "A Tug of War:
  Overnight Versus Intraday Expected Returns") — cited mechanism, not a
  `raw/`-ingested source in this vault (no paper text pinned here; flagged
  if a fuller literature review is wanted later).
