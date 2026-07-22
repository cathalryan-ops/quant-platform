---
type: strategy
created: 2026-07-22
---

# Low-Volatility Anomaly — 50 Single-Name Stocks

First strategy in this vault built on a mechanism other than momentum
(time-series or cross-sectional), market-structure-shift,
mean-reversion, or calendar. Reuses the just-pinned 50-single-name-stock
universe (`sandbox/backtest/DATA.md`) — no new data fetch — and
[[cross-sectional-momentum-stocks50]]'s exact monthly-rebalance,
top_n=15 concentration architecture, but ranks by trailing realized
volatility instead of trailing return, and holds the LEAST volatile
subset instead of the strongest.

## Hypothesis

[[low-volatility-anomaly]]: ranking 50 individual stocks by trailing
1-year realized volatility each month and holding the 15 least volatile
(equal-weighted) captures a real risk-adjusted edge — because
leverage-constrained investors bid up high-vol/high-beta names for
lottery-like upside (Frazzini & Pedersen 2014), low-vol names should earn
a *better*, not merely lower-variance, risk-adjusted return.

Parameters fixed before any backtest ran: `lookback=252` (1 trading
year) — matches the lookback already used by every momentum strategy in
this vault ([[tsmom-spy-qqq]], [[sector-rotation]],
[[cross-sectional-momentum-stocks50]]) for direct comparability, and is
the standard window in the low-vol literature itself (Ang/Hodges/Xing/
Zhang 2006 use 1-year realized vol). No `skip` gap — unlike momentum's
`skip=21` (deliberately excluding the short-term-reversal window), there
is no analogous reason to exclude the most recent month from a
volatility estimate. `top_n=15` (~30% of the universe) — carried over
unchanged from cross-sectional-momentum-stocks50 to preserve the same
concentration ratio sector-rotation established (3 of 10), not
re-derived. Monthly rebalance — same cadence as every other
cross-sectional strategy here. **Long-only, no short leg** — the
canonical Betting Against Beta construction is long-low-vol/
short-high-vol, but every cross-sectional strategy in this vault to date
is long-only; adding a short leg is a genuinely different risk profile
and is NOT implemented here, flagged as an untested follow-up rather
than silently assumed away.

**Killed if:** walk-forward Sharpe (2016-2024, 12 folds, 5 bps fees + 5
bps slippage) fails to clear the standing gate (Sharpe ≥1.0, Sortino
≥1.2). **Also checked:** does the low-vol basket's raw annualized return
merely scale down in proportion to its lower volatility (a
risk-reduction tautology, not an anomaly), or is its risk-adjusted
return (Sharpe) genuinely better than an equal-weight buy-and-hold
benchmark of the same 50-stock universe?

## Mechanism

See [[low-volatility-anomaly]]. Structurally distinct causal story from
every prior mechanism in this vault: not underreaction/continuation
([[time-series-momentum]], [[cross-sectional-momentum]]), not a
mechanical displacement event ([[market-structure-shift]]), but a
capital-constraint mispricing — investors who cannot use leverage buy
high-vol/high-beta names for unlevered lottery-like upside instead,
leaving low-vol names cheap relative to their risk-adjusted return.

## Falsification test

Two checks, run directly against the signal's own output and the raw
universe returns (`scripts/low_vol_anomaly_stocks50_backtest.py`):

1. **Composition stability** — does the least-volatile-15 selection
   rotate across the ~96 monthly rebalances, or collapse onto a
   persistent handful of names?
2. **Return-vs-risk decomposition** — compute the low-vol basket's gross
   annualized return and volatility against an equal-weight
   buy-and-hold of the full 50-stock universe. If the low-vol basket's
   Sharpe is *higher* than the benchmark's, that's the anomaly signature
   (return didn't fall as fast as risk). If its Sharpe is the same or
   lower, the low-vol cut bought lower variance but at a proportional
   (or worse) cost in return — no real edge, just risk reduction.

## Manifest

```strategy_manifest
{
  "schema_version": "1.0.0",
  "id": "low-vol-anomaly-stocks50",
  "wiki_page": "brain/wiki/strategies/low-vol-anomaly-stocks50.md",
  "market": "us_equities",
  "family": "swing",
  "universe": ["AAPL", "ABT", "APD", "AXP", "BA", "BAC", "CAT", "CMCSA", "COP", "CSCO", "CVX", "D", "DIS", "DUK", "ECL", "FCX", "GS", "HD", "HON", "INTC", "JNJ", "JPM", "KO", "MCD", "MRK", "MSFT", "NEE", "NEM", "NKE", "NUE", "O", "ORCL", "OXY", "PEP", "PFE", "PG", "PLD", "PSA", "SBUX", "SLB", "SO", "SPG", "T", "UNH", "UNP", "UPS", "VZ", "WFC", "WMT", "XOM"],
  "hypothesis": "Ranking 50 individual stocks by trailing 1-year realized volatility each month and holding the 15 LEAST volatile (equal-weighted) captures the low-volatility anomaly -- a structurally different mechanism from every prior strategy in this vault (momentum, structure-break, mean-reversion, calendar). Killed if walk-forward Sharpe does not clear 1.0, or if the low-vol basket's return simply scales down with its volatility (no risk-adjusted edge, a tautology not an anomaly).",
  "signal_spec": { "language": "python", "entrypoint": "strategies/low_vol_anomaly_stocks50.py:Signal" },
  "risk": { "max_position_pct": 5.0, "stop_loss_pct": 2.0, "stop_loss_cooldown_sessions": 10 },
  "lifecycle": "retired",
  "scorecard": {
    "sharpe_wf": 0.518773, "sortino_wf": 0.782279, "max_drawdown_bt": 11.471151,
    "sharpe_paper": null, "max_drawdown_paper": null, "pnl_live": null,
    "rank": null
  }
}
```

## Evidence

Real walk-forward backtest (2016-01-01 to 2024-12-31, `folds=12`, real
50-stock Alpaca data, split-adjusted, reusing the pinned
`cross-sectional-momentum-stocks50` snapshot,
`data/results/low-vol-anomaly-stocks50/`): Sharpe 0.518773, Sortino
0.782279, max drawdown 11.471151%, turnover 4.236359 — a clear miss on
the 1.0/1.2 gate, but the best of the three cross-sectional strategies
in this vault so far (vs. sector-rotation's 0.255273 and
cross-sectional-momentum-stocks50's 0.280239). Fold Sharpes: `[0.0,
1.456, 0.186, -0.132, 1.937, -1.001, 1.875, 2.053, -1.358, 1.085, 0.273,
-0.151]` — wide dispersion, five of twelve folds negative. OOS holdout
(trailing 25%, split 2022-09-29): in-sample Sharpe 0.400866, OOS Sharpe
0.257815, a **+35.7% degradation**, REJECTED by the
`oos_reject_threshold=0.35` gate by a hair — the second strategy in this
vault (after [[cross-sectional-momentum-stocks50]]) whose OOS split
degrades rather than improves on in-sample.

Falsification check 1 (composition): 96 of ~108 monthly rebalances
produced a non-empty selection; 61 distinct 15-stock combinations, 37 of
50 stocks selected at least once. Less rotation than
cross-sectional-momentum-stocks50's 93 distinct combos, but not a
single-name-dominance failure either — the persistent core (PEP 100%,
KO 100%, PG 96.9%, JNJ 91.7%, DUK 88.5%, SO 86.5%, MCD 84.4%) is exactly
the classic defensive low-vol sector cluster (staples, utilities,
healthcare) the literature predicts, not an artifact.

Falsification check 2 (**the key finding, and it falsifies the
hypothesis**): gross, cost-free annualized numbers — low-vol-15 basket
ann_return=7.21%, ann_vol=15.04%, raw Sharpe=0.5386; equal-weight
buy-and-hold of the full 50-stock universe: ann_return=10.53%,
ann_vol=17.48%, raw Sharpe=0.6608. The low-vol cut reduced volatility by
14.0% but reduced return by 31.5% — return fell *faster* than risk, and
the low-vol basket's own raw Sharpe is **below** the dumb benchmark's.
Not a tautology (tautology would be proportional decline, same Sharpe);
this is worse than a tautology — a real reversal of the anomaly's
predicted direction on this sample. Full analysis in
[[low-vol-anomaly-2026-07-22]].

## Lifecycle history

- 2026-07-22 — created at `research` — first non-momentum,
  non-structure-break, non-mean-reversion, non-calendar mechanism in
  this vault, direct response to the "new mechanism class" lever chosen
  after both wider-universe ([[universe-scale-2026-07-22]]) and
  extra-blend-leg ([[blend-leg-search-2026-07-22]]) axes closed.
  lookback=252 carried over unchanged from every momentum strategy here
  for comparability and because it's the literature's standard window;
  top_n=15 carried over unchanged from cross-sectional-momentum-stocks50
  for the same concentration ratio. Long-only, no short leg (flagged as
  an explicit scope limit, not an oversight). Reuses the pinned 50-stock
  snapshot — no new data fetch.
- 2026-07-22 — retired — Sharpe 0.518773 / Sortino 0.782279, a clear
  miss but the best cross-sectional result in this vault to date. OOS
  holdout REJECTED (+35.7% degradation, just over the 35% threshold).
  The return-vs-risk decomposition is the real finding: the low-vol
  basket's raw Sharpe (0.5386) is *below* an equal-weight buy-and-hold
  benchmark of the same 50-stock universe (0.6608) — the anomaly not
  only failed to appear, it inverted on this sample. Composition is
  genuine (defensive-sector cluster, not single-name dominance) so this
  isn't an implementation artifact. Not a parameter-tuning target
  (lookback/top_n fixed a priori for comparability, not searched; a
  long-short variant is flagged as the natural next step but is a
  different risk profile, not a fix to this result). See
  [[low-vol-anomaly-2026-07-22]] for the full writeup and what it
  implies about further single-mechanism cross-sectional tests on this
  universe/period.
