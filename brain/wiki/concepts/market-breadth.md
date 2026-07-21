---
type: concept
created: 2026-07-21
---

# Market Breadth

The fraction of a basket's members that are independently confirming a
trend — not to pick which member to hold ([[cross-sectional-momentum]]),
but as an aggregate participation statistic used to confirm or veto a
decision on a *different*, usually broader-index, asset. A rally carried
by a narrow subset of constituents while most lag ("generals leading
without soldiers") is historically associated with fragility and higher
reversal risk than one confirmed by broad participation across the
basket — the premise behind classic breadth-thrust and advance/decline
indicators (Zweig Breadth Thrust; Fosback's *Stock Market Logic*, 1976).

## What matters for us

Every gate this vault has tested so far on [[time-series-momentum]] has
been self-referential — [[volatility-acceleration]] and
[[volatility-targeting]] both look only at the traded asset's OWN price
series (its own realized vol vs. its own baseline). Breadth is the first
gate that looks at OTHER assets entirely, which only became possible once
the wider 16-symbol snapshot pinned a real cross-section (10 SPDR sector
ETFs) to measure participation from. It's a genuinely different causal
story from the vol-gate line too: vol-acceleration asks "is this specific
asset's own move getting more violent?" while breadth asks "is the broad
market backing this move, or is leadership narrowing?" — two different
early-warning signals that could in principle fire at different times.

## Evidence & sources

- Zweig, M. — the Breadth Thrust indicator (popularized in *Winning on
  Wall Street*, 1986) — the canonical breadth-as-confirmation
  construction this vault's [[tsmom-breadth-gate]] implementation
  follows in spirit (participation fraction vs. a fixed threshold), using
  trailing 12-1 momentum sign rather than an advance/decline count as the
  per-constituent "confirming" test, for direct construction reuse with
  [[time-series-momentum]].
- Fosback, N. (1976), *Stock Market Logic* — earlier breadth-thrust
  formulation.
