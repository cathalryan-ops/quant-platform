---
type: strategy
created: 2026-07-21
---

# Sector Rotation — SPDR Sector ETFs

The first genuinely cross-sectional strategy in this vault. Every prior
strategy scored SPY and/or QQQ independently against their own price
history; this one can only be expressed with a basket of assets to rank
against each other, which is exactly what the newly pinned 16-symbol
snapshot (`sandbox/backtest/DATA.md`) exists to unlock.

## Hypothesis

[[cross-sectional-momentum]]: ranking the 10 SPDR sector ETFs (XLK, XLF,
XLE, XLV, XLI, XLY, XLP, XLU, XLB, XLRE) against each other's trailing
return each month and rotating into the relative leaders captures an
edge distinct from [[time-series-momentum]]'s absolute construction —
already tested on SPY/QQQ ([[tsmom-spy-qqq]], Sharpe 0.813, this vault's
best result so far) but never in a form that lets one sector's *relative*
strength against its peers matter, only its own absolute trailing
return.

Parameters fixed before any backtest ran: `lookback=252`, `skip=21` —
identical values to [[tsmom-spy-qqq]], chosen for direct comparability
against the already-recorded absolute-momentum result, not re-derived.
`top_n=3` (hold the 3 strongest of 10 sectors, equal-weighted, ~30% of
the universe) — a standard, round concentration level in the sector-
rotation literature, not fit to this sample. Monthly rebalance (first
trading day of each calendar month) — the standard cross-sectional
momentum cadence, balancing responsiveness against turnover cost.

**Killed if:** walk-forward Sharpe (2016-2024, 12 folds, 5 bps fees + 5
bps slippage) fails to clear the standing gate (Sharpe ≥1.0, Sortino
≥1.2). **Also checked:** does the selected top-3 set actually rotate over
time, or does it collapse onto the same 3 sectors persistently (e.g.
always XLK)? A rotation strategy that never rotates isn't really testing
the cross-sectional claim — it would just be a leveraged bet on whichever
sector happens to dominate the sample.

## Mechanism

See [[cross-sectional-momentum]]. Distinct causal story from
[[time-series-momentum]]'s trend-following/underreaction-to-flow
narrative: cross-sectional rotation is closer to a relative-strength/
capital-allocation story — institutional flows (sector fund rebalancing,
thematic ETF flows, analyst sector-weight recommendations) concentrate in
whichever sectors are already outperforming their peers, reinforcing the
relative ranking over the following month, independent of whether the
broad market itself is up or down.

## Falsification test

Print the selected top-3 set at each of the ~108 monthly rebalances and
check for persistent concentration: if one or two sectors dominate the
vast majority of selections, this is really a concentrated single-sector
bet dressed up as rotation, and any positive result says more about that
sector's specific 2016-2024 performance than about the cross-sectional
momentum mechanism generally.

## Manifest

```strategy_manifest
{
  "schema_version": "1.0.0",
  "id": "sector-rotation",
  "wiki_page": "brain/wiki/strategies/sector-rotation.md",
  "market": "us_equities",
  "family": "swing",
  "universe": ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY"],
  "hypothesis": "Ranking the 10 SPDR sector ETFs against each other's trailing 12-1 momentum each month and rotating into the top 3 (equal-weighted) captures a cross-sectional edge distinct from tsmom-spy-qqq's absolute-momentum construction. Killed if walk-forward Sharpe does not clear 1.0, or if the selected set collapses onto one or two sectors rather than genuinely rotating.",
  "signal_spec": { "language": "python", "entrypoint": "strategies/sector_rotation.py:Signal" },
  "risk": { "max_position_pct": 5.0, "stop_loss_pct": 2.0, "stop_loss_cooldown_sessions": 10 },
  "lifecycle": "retired",
  "scorecard": {
    "sharpe_wf": 0.255273, "sortino_wf": 0.390583, "max_drawdown_bt": 3.1296,
    "sharpe_paper": null, "max_drawdown_paper": null, "pnl_live": null,
    "rank": null
  }
}
```

## Evidence

Real walk-forward backtest (2016-01-01 to 2024-12-31, `folds=12`, real
16-symbol Alpaca data restricted to the 10 sectors,
`data/results/sector-rotation/`): Sharpe 0.255273, Sortino 0.390583, max
drawdown 3.1296% (the highest of any strategy in this vault so far),
turnover 1.524093 (second-highest, after turn-of-month-spy-qqq's 2.39).
A clear miss, not a near-miss. Fold Sharpes swing widely with no
discernible pattern: `[0.0, -0.793, 1.1, -1.199, 0.736, 0.201, 1.916,
-0.774, -0.223, 0.267, 0.75, 1.081]` — five of twelve folds negative. OOS
holdout (trailing 25%, split 2022-09-29): in-sample Sharpe 0.266676, OOS
Sharpe 0.713131 — improves on in-sample again, the same pattern nearly
every strategy in this vault shows on this particular split (suggesting
something about 2022-Q4-onward market conditions broadly favored
long-biased strategies generally, not something specific to this signal).

Falsification check (raw signal, `scripts/sector_rotation_backtest.py`):
94 of ~108 monthly rebalances produced a non-empty selection (the rest
fell in the warm-up period); **32 distinct 3-sector combinations** were
used across those 94 rebalances — the strategy genuinely rotates, this
is not a single-sector bet dressed up as rotation. But selection
frequency is uneven: XLK (technology) was selected in 69.1% of
rebalances, far more than any other sector (next-highest: XLY 37.2%, XLI
36.2%). That's a real, honestly-reported feature of this specific
2016-2024 window (mega-cap tech's well-documented dominance over this
exact period), not a mechanism failure — the falsification test's
specific bar (does it rotate at all) is passed — but it does mean this
result is closer to "cross-sectional momentum mostly found tech and rode
it, with real rotation around the edges" than a broad-based validation of
sector rotation as a mechanism independent of which decade you happen to
test it in.

## Lifecycle history

- 2026-07-21 — created at `research` — first cross-sectional strategy in
  this vault, enabled by the newly pinned 16-symbol snapshot;
  lookback/skip carried over unchanged from tsmom-spy-qqq for direct
  comparability, top_n fixed at a standard round concentration level
  before any backtest run, not searched. Includes
  `stop_loss_cooldown_sessions: 10` (Option C) from the start per
  [[stop-loss-rearm-coupling]].
- 2026-07-21 — retired — Sharpe 0.255273 / Sortino 0.390583, a clear
  miss (not a near-miss like tsmom-spy-qqq's 0.813), with the highest
  drawdown (3.13%) and second-highest turnover (1.52) recorded in this
  vault. The falsification test (does the selection actually rotate) is
  passed cleanly — 32 distinct 3-sector combinations across 94
  rebalances — but XLK's 69.1% selection frequency means much of
  whatever edge exists here is really "correctly identified tech's
  dominance over 2016-2024" rather than a broad cross-sectional-momentum
  effect across all 10 sectors. Structurally worse than the absolute
  time-series momentum result on the same broad market
  ([[tsmom-spy-qqq]], Sharpe 0.813): for this narrow a universe (10
  sectors, not hundreds of individual names) and this coarse a cut
  (monthly rebalance, top-3-of-10, no cost-aware turnover control),
  relative-strength rotation did not outperform simply riding SPY/QQQ's
  own absolute trend. Not a parameter-tuning target (top_n/lookback/skip
  were fixed before running, not searched); if this axis gets revisited,
  the flagged next step is a genuinely larger, more diversified
  cross-sectional universe (dozens to hundreds of names) rather than
  re-tuning the same 10-sector cut.
