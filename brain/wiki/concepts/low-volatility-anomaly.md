---
type: concept
created: 2026-07-22
---

# Low-Volatility Anomaly

Rank a basket by trailing realized volatility and hold the LEAST volatile
subset, equal-weighted — the opposite ranking direction from
[[cross-sectional-momentum]], which ranks by trailing *return* and holds
the strongest. Documented since Ang, Hodges, Xing & Zhang (2006) found
low-volatility stocks earn higher risk-adjusted (and sometimes higher
raw) returns than high-volatility stocks, contradicting the CAPM
prediction that risk and expected return move together. Frazzini &
Pedersen's "Betting Against Beta" (2014) frames the same effect as a
consequence of leverage-constrained investors bidding up high-beta names
for unlevered lottery-like upside, leaving low-beta/low-vol names cheap
relative to their risk-adjusted return — a capital-constraint story,
structurally distinct from [[time-series-momentum]]'s
underreaction-to-flow narrative or [[market-structure-shift]]'s
mechanical displacement-event story.

## What matters for us

The first mechanism tested in this vault that is neither momentum
(time-series or cross-sectional), market-structure-shift,
mean-reversion, nor calendar — see [[low-vol-anomaly-stocks50]]. Needs
only close prices (already pinned for every universe in this vault), no
fundamentals, so it was directly testable without a new data fetch. The
canonical construction (Betting Against Beta) is long-low-vol/
short-high-vol; this vault's first test is long-only-least-volatile-15,
matching every other cross-sectional strategy here
([[cross-sectional-momentum]]) for direct comparability — the
long-short variant is a distinct, untested risk profile.

## Evidence & sources

- Ang, A., Hodges, R., Xing, Y. and Zhang, X. (2006), "The Cross-Section
  of Volatility and Expected Returns", *Journal of Finance* — documents
  higher risk-adjusted returns for low-volatility stocks vs. the CAPM
  prediction.
- Frazzini, A. and Pedersen, L.H. (2014), "Betting Against Beta",
  *Journal of Financial Economics* — leverage-constraint explanation,
  canonical long-low-beta/short-high-beta construction.
- [[low-vol-anomaly-stocks50]] — this vault's first test: Sharpe
  0.518773, and the return-vs-risk decomposition found the anomaly does
  NOT hold on this 50-stock/2016-2024 sample — the low-vol basket's raw
  Sharpe (0.5386) is actually *below* an equal-weight buy-and-hold
  benchmark of the same universe (0.6608). See
  [[low-vol-anomaly-2026-07-22]] for the full writeup.
