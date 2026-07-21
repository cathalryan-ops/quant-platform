# Brain Index

Catalog of every wiki page. Maintained by the vault operations (`/capture`,
`/sync`, `/lint`) — see `brain/CLAUDE.md`.

## Strategies

- [[ms-shift-spy]] — ms_shift on SPY/QQQ; displacement-filtered
  structure breaks; `retired` (failed backtest→paper gate, real 2016-2024
  data; see Lifecycle history for the fold-regime follow-up).
- [[ms-shift-spy-high-displacement]] — v2, single-variable follow-up
  raising the displacement threshold 1.5x→2.0x ATR; `retired` (Sharpe
  0.813, close on Sortino but still failed the gate — see Lifecycle
  history for the stop-loss-gap finding it points to next).
- [[mean-reversion-spy-qqq]] — structurally distinct from `ms_shift`: buys
  an outsized single-day drop, holds a fixed 5-session horizon; `retired`
  (Sharpe 0.023 — no gate near-miss, and the mechanism-level test found no
  real reversion effect at all).
- [[ms-shift-spy-vol-regime]] — v1's unchanged signal gated to a trailing
  volatility band [12%, 35%] instead of v2's displacement-magnitude axis;
  `retired` (Sharpe 0.120, worse than v1's ungated baseline — the gate
  preserved the strong folds but turned previously-positive folds
  negative).
- [[tsmom-spy-qqq]] — structurally orthogonal to the whole `ms_shift`/
  mean-reversion line: 12-1 time-series momentum, no day-scale event, held
  for as long as the trailing 12-month trend stays positive; `retired`
  (Sharpe 0.813 misses the gate by the same margin as v2, but Sortino
  clears 1.2 and OOS improves on in-sample with zero fit parameters — a
  clean near-miss, not a fitted one — though the pre-registered
  falsification test also triggers: fully invested through the 2020
  COVID crash).
- [[tsmom-vol-accel]] — single-variable follow-up to tsmom-spy-qqq: gates
  the unchanged signal off when 5-day realized vol expands past 1.75x its
  63-day baseline, aimed at tsmom's COVID-crash blind spot; `retired`
  (Sharpe 0.534, worse than the ungated baseline — the gate genuinely
  raised COVID-window flat time from 0% to ~47% as designed, but more
  than doubled turnover, and the added whipsaw cost outweighs the
  crash-window benefit).
- [[tsmom-vol-accel-hysteresis]] — single-variable follow-up to
  tsmom-vol-accel: adds a lower re-entry threshold (1.25 vs the unchanged
  1.75 exit) to cut gate chatter; `retired` (Sharpe 0.608 — every
  prediction came true in direction, turnover down 13.4%, COVID
  protection preserved and improved, but the magnitude wasn't enough to
  close the gap to the ungated baseline; axis closed, flagged next step
  is continuous vol-targeting sizing instead of a binary gate).
- [[tsmom-vol-target]] — structurally different follow-up to the whole
  vol-gate line: replaces the binary gate with continuous vol-targeted
  sizing (`min(1.0, 0.15/realized_vol)`); `retired` (Sharpe 0.742 —
  turnover problem fully solved (0.496, essentially the ungated
  baseline's 0.465) and COVID exposure genuinely scaled down (~39% avg
  weight), but still short of the ungated baseline because raw vol level
  scales down good high-vol folds along with bad ones; closes the
  vol-overlay branch of the momentum line with a clean, complete finding).
- [[turn-of-month-spy-qqq]] — first calendar-only hypothesis, no price
  data at all: long the last trading day of the month through the first
  three of the next; `retired` (Sharpe 0.022, a clean null — the
  falsification test failed outright, in-window returns mildly *lower*
  than out-of-window on both symbols, no trace of the effect in this
  sample).
- [[52wk-high-spy-qqq]] — structurally different construction from
  tsmom: price-to-rolling-max ratio (anchoring-bias mechanism, George &
  Hwang 2004) rather than a trailing return; `retired` (Sharpe 0.625,
  meaningfully below tsmom-spy-qqq's 0.813 — ~80% raw-signal agreement
  with tsmom means this is a related but not fully independent bet, and
  it nets out worse with more than double the turnover, suggesting the
  max-ratio construction chatters near its threshold more).
- [[sector-rotation]] — first cross-sectional strategy in this vault:
  ranks the 10 SPDR sector ETFs against each other monthly, holds the
  top 3; `retired` (Sharpe 0.255, a clear miss, highest drawdown and
  second-highest turnover recorded here — genuinely rotates (32 distinct
  3-sector combinations) but XLK dominates 69.1% of selections, so this
  mostly found tech's 2016-2024 dominance rather than validating
  cross-sectional momentum broadly).

## Concepts

- [[market-structure-shift]] — decisive break of the prevailing swing
  sequence; core setup of the `ms_shift` family.
- [[displacement]] — wide-range confirmation of a break; the quality filter
  for structure shifts.
- [[stop-loss-rearm-coupling]] — why gating a stop's re-arm on the same
  rare event a trend-persistent signal uses to reverse can lock a position
  out of the exact recovery that would have vindicated it; the "Option C"
  fix and its OOS validation on ms-shift-spy-v1/v2.
- [[time-series-momentum]] — an asset's own trailing return predicts its
  near-term drift; absolute (not cross-sectional), month-scale, and blind
  to shocks inside its own lookback window.
- [[volatility-acceleration]] — short-window realized vol vs. its own
  longer-window baseline; a fast, relative, self-referential regime-change
  detector, distinct from a static absolute vol band.
- [[volatility-targeting]] — continuous, threshold-free position scaling
  inversely with realized vol; no gate to chatter across, but doesn't
  distinguish "good" (rally) vol from "bad" (crash) vol.
- [[turn-of-month-effect]] — returns cluster around month boundaries
  (institutional-flow-driven, not information-driven); the first
  calendar-only, price-independent mechanism tested in this vault.
- [[fifty-two-week-high-effect]] — price proximity to its own trailing
  52-week high predicts continuation via anchoring bias, a different
  causal claim (and different arithmetic — ratio to a rolling max, not a
  trailing return) than [[time-series-momentum]].
- [[cross-sectional-momentum]] — rank a basket against EACH OTHER's
  trailing return and rotate into the relative leaders, as opposed to
  time-series-momentum's absolute (judge-against-own-history)
  construction; the first mechanism in this vault needing a basket, not
  a single asset.

## Postmortems

- [[ms-shift-spy-example]] — worked-example paper review for
  ms-shift-spy-v1 (P9 template demonstration).
