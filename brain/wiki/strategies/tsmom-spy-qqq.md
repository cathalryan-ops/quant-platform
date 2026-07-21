---
type: strategy
created: 2026-07-21
---

# Time-Series Momentum — SPY/QQQ

A structurally orthogonal follow-up to the whole `ms_shift`/mean-reversion
line so far: every prior strategy in this vault ([[ms-shift-spy]],
[[ms-shift-spy-high-displacement]], [[ms-shift-spy-vol-regime]],
[[mean-reversion-spy-qqq]]) traded a day-scale event (a confirmed swing
break, a single-session shock) with a fixed or short holding period. This
strategy has no such event at all: it holds SPY and/or QQQ for however
long each one's own trailing 12-month trend stays positive.

## Hypothesis

[[time-series-momentum]]: SPY and QQQ's own trailing 12-month return,
measured with a 1-month skip to net out short-term reversal, predicts the
sign of near-term drift. Long-only (v1 protocol constraint): long a
symbol while its trailing momentum is positive, flat (cash) otherwise,
scored independently per symbol so the two can be long, flat, or one of
each at any time.

Parameters fixed before any backtest ran: `lookback=252` trading days
(~12 months), `skip=21` trading days (~1 month) — both the standard
academic construction (Moskowitz/Ooi/Pedersen 2012), not fit to this
dataset. No holding-period parameter exists to fit: the position simply
tracks the sign of trailing momentum every session.

**Killed if:** walk-forward Sharpe (2016-2024, 12 folds, 5 bps fees + 5
bps slippage) fails to clear the standing `backtest_to_paper` gate
(Sharpe ≥1.0, Sortino ≥1.2). **Also killed** (mechanism-level, not just a
near-miss) if the strategy is *in* the market through the two largest
drawdown events in-sample (the 2020-02/03 COVID crash, the 2022 bear
market) rather than flat during them — since staying out of sustained
downtrends is the entire mechanism this hypothesis relies on, being long
through them would mean the signal isn't doing what it claims regardless
of the aggregate Sharpe number.

## Mechanism

Why would this edge exist, distinct from every mechanism already tested
here? [[time-series-momentum]] usually cites underreaction to information
that gets impounded into prices slowly (analyst/investor anchoring,
gradual institutional flow rebalancing into winners) plus trend-following
strategies themselves (CTAs, risk-parity vol-targeting funds delevering
into drawdowns) mechanically reinforcing the move once it's underway —
both are month-scale, flow-driven stories, not the single-session
liquidity/participant stories behind [[market-structure-shift]] or
mean-reversion. The "who's on the other side" answer here is specifically
investors who rebalance on a fixed calendar schedule or against a
valuation anchor regardless of trend (classic contrarian value rebalancing
into a falling market, or simply not rebalancing at all) — they give up
exactly the drift this signal captures.

## Falsification test

The cheapest, most direct check: plot which sessions the strategy is
flat vs. long against SPY/QQQ's own price series and confirm the flat
periods actually cover the 2020 COVID crash and the bulk of the 2022
drawdown — not just eyeball the aggregate Sharpe. If the strategy is long
through those and flat during calm uptrends instead, the sign convention
or lookback/skip arithmetic is inverted or broken, and the result is
meaningless regardless of what the number reads.

## Manifest

```strategy_manifest
{
  "schema_version": "1.0.0",
  "id": "tsmom-spy-qqq",
  "wiki_page": "brain/wiki/strategies/tsmom-spy-qqq.md",
  "market": "us_equities",
  "family": "swing",
  "universe": ["SPY", "QQQ"],
  "hypothesis": "SPY and QQQ's own trailing 12-month return (skipping the most recent month) predicts the sign of near-term drift; long-only, scored independently per symbol, held for however long the trend stays positive. Killed if walk-forward Sharpe does not clear 1.0, or if the strategy is long (not flat) through the 2020 COVID crash and 2022 bear market.",
  "signal_spec": { "language": "python", "entrypoint": "strategies/tsmom_spy_qqq.py:Signal" },
  "risk": { "max_position_pct": 5.0, "stop_loss_pct": 2.0, "stop_loss_cooldown_sessions": 10 },
  "lifecycle": "retired",
  "scorecard": {
    "sharpe_wf": 0.813366, "sortino_wf": 1.216489, "max_drawdown_bt": 2.305277,
    "sharpe_paper": null, "max_drawdown_paper": null, "pnl_live": null,
    "rank": null
  }
}
```

## Evidence

Real walk-forward backtest (2016-01-01 to 2024-12-31, `folds=12`, real
SPY+QQQ Alpaca data, `data/results/tsmom-spy-qqq/`): Sharpe 0.813366,
Sortino 1.216489, max drawdown 2.305277% (turnover 0.465489). **Sortino
clears the 1.2 gate**; Sharpe misses the 1.0 gate. OOS holdout (trailing
25%, split 2022-09-29): in-sample Sharpe 0.593616, OOS Sharpe 1.123882 —
OOS *improves* on in-sample, about as clean a non-overfit signature as
this vault has produced (no free parameter was fit to this sample at all
— lookback/skip are the fixed academic values). Fold Sharpes: `[0.0,
1.446, 1.197, -0.405, 1.237, 0.179, 1.816, 1.771, -1.223, 1.27, 1.2,
1.272]` — only two clearly negative folds out of twelve, one (fold 8,
-1.223) coinciding with the 2022 whipsaw.

Falsification check (raw signal, `scripts/tsmom_backtest.py`): during the
2020 COVID crash window (2020-02-19 to 2020-04-07), the strategy was
**0% flat** — fully invested through the entire crash on both SPY and
QQQ. During the 2022 bear market window (2022-01-03 to 2022-10-12), it
was flat 48.0% of sessions on SPY and 52.0% on QQQ. This is a genuine
mechanism limitation, not a sign the signal is broken or inverted: a
12-month trailing-return signal is blind to a shock that occurs *within*
its own lookback window — going into February 2020, trailing momentum
was strongly positive off 2019's rally, and the crash itself hadn't yet
entered the (skip-adjusted) measurement window, so there was no way for
this signal to have anticipated it. The 2022 decline was a multi-month
grind, which the same signal *did* substantially sit out. Time-series
momentum structurally protects against slow bleeds, not fast shocks —
consistent with the wider literature on trend-following (e.g. the same
funds this concept describes are well known to get caught by the initial
leg of sharp crashes and only de-risk afterward), not evidence against
the hypothesis itself. Recorded as a real, pre-registered falsification
trigger below regardless, since that was the bar this page committed to
before running the backtest.

## Lifecycle history

- 2026-07-21 — created at `research` — proposed as a structurally
  orthogonal follow-up to the entire day-scale line tested so far
  (structure-break continuation, single-session mean-reversion);
  lookback/skip fixed before any backtest run at the standard academic
  12-1 values, not searched. Includes `stop_loss_cooldown_sessions: 10`
  (Option C) from the start per [[stop-loss-rearm-coupling]].
- 2026-07-21 — retired — Sharpe 0.813366 misses the 1.0 gate (Sortino
  1.216489 clears 1.2; max drawdown 2.305277% is well inside the 15%
  cap) — a near-miss on the same order as
  [[ms-shift-spy-high-displacement]]'s (Sharpe 0.813341), but reached by
  a structurally unrelated mechanism with zero fit parameters and an
  OOS split that *improves* on in-sample rather than degrading. The
  pre-registered falsification test also formally triggers: the
  strategy was fully invested (0% flat) through the entire 2020 COVID
  crash window on both symbols, even though it did sit out roughly half
  of the 2022 grinding bear market. Read together: the gate failure and
  the falsification trigger both point at the same real limitation
  (trailing momentum can't see a shock inside its own lookback window),
  not a backwards or broken signal — this family only guards slow
  downtrends, and the aggregate Sharpe reflects that limitation
  honestly. Not a parameter-tuning target on this sample (lookback/skip
  were never fit here to begin with); a genuinely different mechanism —
  e.g. one that responds to realized-vol acceleration rather than only
  trailing return — is the right next step if this axis gets revisited.
