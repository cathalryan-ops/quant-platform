---
type: strategy
created: 2026-07-21
---

# Turn-of-Month — SPY/QQQ

A mechanism class none of this vault's prior strategies have tested: a
pure calendar effect, no price/volatility state at all. Structurally as
orthogonal as it gets from [[market-structure-shift]] (day-scale
structure breaks), [[mean-reversion-spy-qqq]] (single-session shocks),
[[time-series-momentum]] (multi-month trailing return), and the whole
[[volatility-acceleration]]/[[volatility-targeting]] line — none of which
this signal shares any input, state, or assumption with.

## Hypothesis

[[turn-of-month-effect]]: SPY and QQQ returns are disproportionately
concentrated in a window around month boundaries. Long-only, both symbols
identically (there's no reason a purely calendar-driven effect would
differ between two broad-index ETFs): long during the window, flat
(cash) otherwise.

Parameters fixed before any backtest ran, both the classic
Lakonishok & Smidt (1988) four-day academic definition, not fit to this
dataset: `days_before_month_end=1` (the last trading day of the month),
`days_into_next_month=3` (the first three trading days of the next).
Implemented as a calendar-day approximation of the trading-day window
(day-of-month vs. days-in-month, computed per-row from each date alone,
never from neighboring rows) — this will be off by a session or two in
months where the calendar month-end falls on a weekend, a deliberate
simplification traded for being trivially, unconditionally lookahead-safe
(the signal doesn't touch price data at all). Not expected to
meaningfully bias the result either direction; noted honestly as a
limitation rather than hidden.

**Killed if:** walk-forward Sharpe (2016-2024, 12 folds, 5 bps fees + 5
bps slippage) fails to clear the standing gate (Sharpe ≥1.0, Sortino
≥1.2) — same bar as every strategy in this vault. **Also killed** if the
strategy's return pattern shows no visible concentration relative to a
naive expectation (with the window covering 4 of ~21 trading days per
month, roughly 19% of sessions, a genuine effect should contribute
noticeably more than 19% of total return) — a Sharpe near zero from
simply being in cash most of the time isn't informative either way, but a
Sharpe that's positive only because of the trading-days-invested discount
rather than real return concentration would be.

## Mechanism

See [[turn-of-month-effect]]. Institutional-flow-driven, not
information-driven: month-end/month-start pension and retirement-account
contribution cycles, portfolio rebalancing concentrated at reporting-
period boundaries, and payday-linked flows are the standard proposed
causes — none of which requires the price series itself to contain
predictive information, unlike every trend/structure/volatility
hypothesis already tested here.

## Falsification test

Compare average daily return inside the window vs. outside it, directly,
not just the aggregate Sharpe: the hypothesis specifically predicts
excess return concentration in ~19% of sessions. If in-window and
out-of-window average returns are statistically indistinguishable, the
effect isn't present in this sample regardless of what the walk-forward
Sharpe happens to read (a Sharpe near the gate driven by noise in a small
number of sessions would be a false positive on this narrower test).

## Manifest

```strategy_manifest
{
  "schema_version": "1.0.0",
  "id": "turn-of-month-spy-qqq",
  "wiki_page": "brain/wiki/strategies/turn-of-month-spy-qqq.md",
  "market": "us_equities",
  "family": "swing",
  "universe": ["SPY", "QQQ"],
  "hypothesis": "SPY and QQQ returns are disproportionately concentrated in a window around month boundaries (last trading day of the month through the first three of the next); long-only, identical for both symbols, flat outside the window. Killed if walk-forward Sharpe does not clear 1.0, or if in-window average return is not distinguishably higher than out-of-window average return.",
  "signal_spec": { "language": "python", "entrypoint": "strategies/turn_of_month_spy_qqq.py:Signal" },
  "risk": { "max_position_pct": 5.0, "stop_loss_pct": 2.0, "stop_loss_cooldown_sessions": 10 },
  "lifecycle": "retired",
  "scorecard": {
    "sharpe_wf": 0.021506, "sortino_wf": 0.30264, "max_drawdown_bt": 1.325044,
    "sharpe_paper": null, "max_drawdown_paper": null, "pnl_live": null,
    "rank": null
  }
}
```

## Evidence

Real walk-forward backtest (2016-01-01 to 2024-12-31, `folds=12`, real
SPY+QQQ Alpaca data, `data/results/turn-of-month-spy-qqq/`): Sharpe
0.021506, Sortino 0.30264, max drawdown 1.325044% — a clean null on the
same order as [[mean-reversion-spy-qqq]]'s 0.02269. Turnover 2.392517 is
the highest of any strategy in this vault (a ~4-day window recurring
every month means roughly 100+ round trips over the sample). Fold
Sharpes swing both directions with no discernible pattern: `[-0.767,
-0.547, 0.426, -0.983, -0.059, 2.015, 0.169, 0.567, -0.982, -0.162,
-0.685, 1.266]`. OOS holdout (trailing 25%, split 2022-09-29): in-sample
Sharpe 0.134142, OOS Sharpe 0.118056 — both essentially zero, consistent
with each other (nothing to overfit when there's no signal to begin
with).

Falsification check (raw signal, `scripts/turn_of_month_backtest.py`):
12.9% of sessions fell in-window (lower than the naive ~19% estimate —
the calendar-day approximation undercounts whenever a calendar month-end
lands on a weekend, since no trading day exists in that gap). Average
daily return in-window vs. out-of-window:

| symbol | in-window (annualized) | out-of-window (annualized) |
|---|---|---|
| SPY | 12.90% | 13.61% |
| QQQ | 15.79% | 20.32% |

**The falsification test fails cleanly, in the direction opposite the
hypothesis**: in-window returns are not elevated on either symbol —
they're mildly *lower* than the rest of the month, most noticeably on
QQQ (15.79% vs 20.32%). There is no detectable turn-of-month
concentration in this sample at all, not even a near-miss.

## Lifecycle history

- 2026-07-21 — created at `research` — first calendar-only hypothesis in
  this vault, structurally orthogonal to every price/volatility-derived
  strategy tested so far; window fixed at the classic academic four-day
  definition before any backtest run, not searched. Includes
  `stop_loss_cooldown_sessions: 10` (Option C) from the start per
  [[stop-loss-rearm-coupling]].
- 2026-07-21 — retired — Sharpe 0.021506, a clean null matching
  mean-reversion-spy-qqq's. The mechanism-level falsification test failed
  outright, not just narrowly: in-window average returns were mildly
  *lower* than out-of-window on both symbols (most visibly QQQ: 15.79%
  vs. 20.32% annualized) rather than elevated as the hypothesis
  predicted. Consistent with a well-documented pattern in the academic
  literature (e.g. McLean & Pontiff 2016) that historical calendar
  anomalies tend to weaken or disappear once well known and arbitraged
  against — this vault's SPY/QQQ sample (2016-2024) shows no trace of it.
  Not a parameter-tuning target (the window is the standard academic
  definition, not something to re-fit on a null result); no further
  calendar-effect variant is flagged as a next step on this specific
  axis.
