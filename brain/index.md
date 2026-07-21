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

## Postmortems

- [[ms-shift-spy-example]] — worked-example paper review for
  ms-shift-spy-v1 (P9 template demonstration).
