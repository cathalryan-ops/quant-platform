---
type: strategy
created: 2026-07-22
---

# Cross-Sectional Momentum — 50 Single-Name Stocks

Direct follow-up to [[sector-rotation]]'s flagged next step: "a genuinely
larger, more diversified cross-sectional universe (dozens to hundreds of
names) rather than re-tuning the same 10-sector cut." `sector-rotation.py`'s
`Signal` was already proven universe-agnostic (it ranks whatever's in
`bars.columns`) but was only ever tested on 10 SPDR sector ETFs — aggregates
that `pinned-universe-diversity-2026-07-22` found load almost entirely on
one PC1 factor (71.7% of variance). This runs the identical mechanism on a
newly pinned 50-single-name-stock universe (`sandbox/backtest/DATA.md`),
~4-5 names per GICS sector, to test whether real idiosyncratic dispersion
at scale changes the result.

## Hypothesis

[[cross-sectional-momentum]]: ranking 50 individual stocks against each
other's trailing 12-1 momentum each month and rotating into the top 15
(equal-weighted) finds a materially different result than the same
mechanism found on 10 sector-ETF aggregates ([[sector-rotation]], Sharpe
0.255273 — a clear miss) — because single names carry real idiosyncratic
return dispersion that sector ETFs, themselves diversified baskets, wash
out before the ranking ever sees it.

Parameters fixed before any backtest ran: `lookback=252`, `skip=21` —
identical values to every prior momentum strategy in this vault
([[tsmom-spy-qqq]], [[sector-rotation]]), for direct comparability, not
re-derived. `top_n=15` (hold the top 15 of 50, ~30% of the universe) —
chosen to preserve sector-rotation's own ~30% concentration ratio (3 of
10), not the literal integer 3, which on 50 names would be a ~6% cut, a
different (far more concentrated) bet, not the same mechanism carried
over. Monthly rebalance — same cadence as sector-rotation.

**Killed if:** walk-forward Sharpe (2016-2024, 12 folds, 5 bps fees + 5
bps slippage) fails to clear the standing gate (Sharpe ≥1.0, Sortino
≥1.2). **Also checked:** does the top-15 selection actually rotate across
many of the 50 names over time, or collapse onto a persistent handful —
the same falsification bar sector-rotation applied to its 10-sector
selection, scaled to 50 names.

## Mechanism

See [[cross-sectional-momentum]] and [[sector-rotation]]'s Mechanism
section — identical relative-strength/capital-allocation causal story,
unchanged. The only variable under test here is universe composition:
does the mechanism's edge (or lack of one) depend on ranking sector
aggregates versus ranking the individual stocks those aggregates are
built from?

## Falsification test

Print the selected top-15 set at each of the ~108 monthly rebalances and
check for persistent concentration, same bar sector-rotation applied:
does a small handful of names dominate nearly every selection (which
would mean scaling the universe up didn't actually buy more
cross-sectional dispersion than the 16-symbol/10-sector version did), or
does the selection genuinely spread across most of the 50 names over
time?

## Manifest

```strategy_manifest
{
  "schema_version": "1.0.0",
  "id": "cross-sectional-momentum-stocks50",
  "wiki_page": "brain/wiki/strategies/cross-sectional-momentum-stocks50.md",
  "market": "us_equities",
  "family": "swing",
  "universe": ["AAPL", "ABT", "APD", "AXP", "BA", "BAC", "CAT", "CMCSA", "COP", "CSCO", "CVX", "D", "DIS", "DUK", "ECL", "FCX", "GS", "HD", "HON", "INTC", "JNJ", "JPM", "KO", "MCD", "MRK", "MSFT", "NEE", "NEM", "NKE", "NUE", "O", "ORCL", "OXY", "PEP", "PFE", "PG", "PLD", "PSA", "SBUX", "SLB", "SO", "SPG", "T", "UNH", "UNP", "UPS", "VZ", "WFC", "WMT", "XOM"],
  "hypothesis": "Ranking 50 individual stocks (~4-5 per GICS sector) against each other's trailing 12-1 momentum each month and rotating into the top 15 (equal-weighted) tests whether real single-name idiosyncratic dispersion, unavailable in sector-rotation's 10-ETF universe, changes the cross-sectional-momentum result. Killed if walk-forward Sharpe does not clear 1.0, or if the selected set collapses onto a persistent handful of names rather than genuinely rotating.",
  "signal_spec": { "language": "python", "entrypoint": "strategies/cross_sectional_momentum_stocks50.py:Signal" },
  "risk": { "max_position_pct": 5.0, "stop_loss_pct": 2.0, "stop_loss_cooldown_sessions": 10 },
  "lifecycle": "retired",
  "scorecard": {
    "sharpe_wf": 0.280239, "sortino_wf": 0.425607, "max_drawdown_bt": 8.316661,
    "sharpe_paper": null, "max_drawdown_paper": null, "pnl_live": null,
    "rank": null
  }
}
```

## Evidence

Real walk-forward backtest (2016-01-01 to 2024-12-31, `folds=12`, real
50-stock Alpaca data, split-adjusted, `data/results/cross-sectional-momentum-stocks50/`):
Sharpe 0.280239, Sortino 0.425607, max drawdown 8.316661%, turnover
7.858997 — a clear miss on the 1.0/1.2 gate, in the same order of
magnitude as [[sector-rotation]]'s 0.255273/0.390583 on 10 sector ETFs.
Fold Sharpes: `[0.0, -1.955, 1.318, -0.312, 1.385, 0.24, 1.819, 0.092,
-0.051, 0.605, -0.008, 0.23]` — five of twelve folds negative, no
discernible regime pattern, similar shape to sector-rotation's own fold
spread. OOS holdout (trailing 25%, split 2022-09-29): in-sample Sharpe
0.53059, OOS Sharpe 0.295872 — a **-44.2% degradation**, REJECTED by the
`oos_reject_threshold=0.35` gate — the first strategy in this vault where
the OOS split does not improve on in-sample (every prior walk-forward
result with an OOS check showed the opposite).

Falsification check (`scripts/cross_sectional_momentum_stocks50_backtest.py`):
94 of ~108 monthly rebalances produced a non-empty selection; **93
distinct 15-stock combinations** across those 94 rebalances, and **all 50
of 50 stocks were selected at least once** — a materially cleaner
rotation result than sector-rotation's own (32 distinct combos of 10
sectors, with XLK dominating 69.1% of selections). Most-selected single
name here, MSFT, appears in 73.4% of rebalances — comparable to XLK's
dominance, but the frequency curve tails off smoothly across the
remaining names rather than concentrating, and every name in the universe
gets used. The mechanism genuinely finds broad-based cross-sectional
rotation on this universe; that just doesn't translate into a better
Sharpe, and comes with ~5x sector-rotation's turnover. Full analysis in
[[universe-scale-2026-07-22]].

## Lifecycle history

- 2026-07-22 — created at `research` — direct follow-up to
  [[sector-rotation]]'s flagged next step and
  `pinned-universe-diversity-2026-07-22`'s PC1-concentration finding.
  lookback/skip carried over unchanged from tsmom-spy-qqq/sector-rotation
  for direct comparability; top_n=15 fixed a priori by the
  concentration-ratio argument above (matches sector-rotation's ~30%
  cut), not searched. Includes `stop_loss_cooldown_sessions: 10` (Option
  C) from the start per [[stop-loss-rearm-coupling]], matching every
  strategy proposed since that fix.
- 2026-07-22 — retired — Sharpe 0.280239 / Sortino 0.425607, a clear miss
  in the same order of magnitude as sector-rotation's own 0.255273 — a
  5x larger, genuinely more diverse universe did not move the Sharpe.
  The falsification test passed more cleanly than sector-rotation's ever
  did (93 distinct 15-stock combinations across 94 rebalances, all 50
  names selected at least once, no single-name dominance analogous to
  XLK's 69.1%) — ruling out "the mechanism only ever found one dominant
  name" as an explanation. Turnover (7.858997) is ~5x sector-rotation's
  and drawdown (8.32%) is worse (3.13%), and this is the first strategy
  in this vault whose OOS holdout Sharpe degrades rather than improves
  on in-sample (-44.2%, REJECTED by the OOS gate). Not a
  parameter-tuning target (top_n/lookback/skip fixed a priori per the
  concentration-ratio argument, not searched). Closes the
  "genuinely-larger-universe" lever flagged by both sector-rotation and
  dual-momentum-equity-bond-gold and posed as the open question in both
  2026-07-22 digests — see [[universe-scale-2026-07-22]] for the full
  writeup. Flagged next step: a different mechanism class, or a pause on
  further recombination against these same fixed 2016-2024 windows,
  rather than scaling the universe again.
