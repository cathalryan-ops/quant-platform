---
type: concept
created: 2026-07-22
---

# Pairs Trading / Statistical Arbitrage

Relative-value mean-reversion between two historically co-moving assets:
form a spread (one asset minus a hedge-ratio-weighted multiple of the
other), and when the spread diverges from its own recent mean, bet on its
convergence — long the cheap leg, short the rich leg, market-neutral by
construction. The classical reference is Gatev, Goetzmann & Rouwenhorst
(2006), "Pairs Trading: Performance of a Relative-Value Arbitrage Rule";
the underlying statistical requirement — the spread must be *stationary*,
i.e. the two price series are cointegrated, not merely correlated — is
Engle & Granger (1987), "Co-Integration and Error Correction".

## What matters for us

Structurally distinct from every mean-reversion mechanism already tested
here. [[mean-reversion-spy-qqq]] (a confirmed mechanism-level null,
Sharpe 0.023) is *absolute*: one asset's own price reverting to its own
recent level after an outsized single-day move. Pairs trading is
*relative*: it never makes a directional bet on either asset's own price
level, only on the spread between two assets converging — so a
single-asset null says nothing about whether this mechanism works, and a
different single-asset null wouldn't need to falsify it either. It's also
the first genuinely market-neutral (long-short) construction in this
vault; every prior cross-sectional strategy ([[cross-sectional-momentum]],
[[low-volatility-anomaly]]) is long-only.

Two failure modes specific to this mechanism, both checked directly in
[[pairs-trading-stocks50]]'s falsification test: (1) the pair might not
actually be cointegrated, just correlated over the screening window by
chance (spurious regression) — guarded against with a pre-registered
Engle-Granger significance threshold rather than picking winners after
the fact; (2) even a genuinely cointegrated relationship can break down
mid-sample (a merger, a regulatory divergence, a permanent re-rating of
one name relative to its peer) — checked by comparing cointegration
strength in the first vs. second half of the backtest window.

## Evidence & sources

- Gatev, E., Goetzmann, W.N. and Rouwenhorst, K.G. (2006), "Pairs
  Trading: Performance of a Relative-Value Arbitrage Rule", *Review of
  Financial Studies* — the canonical formation/trading-period
  construction and its historical performance.
- Engle, R.F. and Granger, C.W.J. (1987), "Co-Integration and Error
  Correction: Representation, Estimation, and Testing", *Econometrica* —
  the statistical test (residual stationarity of an OLS-regressed spread)
  used to screen candidate pairs here.
- [[pairs-trading-stocks50]] — this vault's first test, on same-sector
  pairs from the pinned 50-stock universe.
