---
type: concept
created: 2026-07-21
---

# Turn-of-Month Effect

A well-documented seasonal anomaly: equity index returns are
disproportionately concentrated in a narrow window around month
boundaries — classically the last trading day of the month through the
first few trading days of the next (Ariel 1987; Lakonishok & Smidt 1988's
four-day definition). Outside that window, average returns are close to
flat historically. A pure calendar effect — no price history, trend, or
volatility state involved at all.

## What matters for us

Every other strategy in this vault ([[market-structure-shift]],
[[time-series-momentum]], [[volatility-acceleration]],
[[volatility-targeting]]) conditions on price action or realized
volatility. This is the first mechanism class tested here that doesn't:
the signal is a pure function of the calendar date, structurally
orthogonal to everything else — a useful diversification check on
whether this vault's null results so far reflect something about SPY/QQQ
specifically or about price-derived signals specifically.

Proposed causal stories in the literature are institutional-flow-driven:
month-end/month-start pension and 401(k) contribution cycles, portfolio
rebalancing and window dressing concentrated at reporting-period
boundaries, and payday-linked retail flows — none of which requires any
information content in the price series itself, only public calendar
knowledge.

## Evidence & sources

- Ariel, R. (1987), "A Monthly Effect in Stock Returns", *Journal of
  Financial Economics*.
- Lakonishok, J. and Smidt, S. (1988), "Are Seasonal Anomalies Real? A
  Ninety-Year Perspective", *Review of Financial Studies* — the four-day
  window (last trading day + first three) this vault's
  [[turn-of-month-spy-qqq]] implementation follows.
