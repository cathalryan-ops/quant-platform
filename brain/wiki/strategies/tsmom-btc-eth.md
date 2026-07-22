---
type: strategy
created: 2026-07-22
---

# Time-Series Momentum — BTC/USD, ETH/USD

The first strategy in this vault on a market other than `us_equities`.
Not a new mechanism: [[research-campaign-2026-07-21]] and
[[pinned-universe-diversity-2026-07-22]] together show 13 real
walk-forward backtests, spanning day-scale structure breaks, day-scale
mean-reversion, month-scale absolute and cross-sectional momentum, and a
calendar-only effect, all converging on a Sharpe ~0.6–0.9 ceiling on the
*same* US-equity/sector daily universe — a pattern across structurally
unrelated mechanisms that looks like a property of the data/universe,
not of signal design. This tests that directly by holding the mechanism
fixed and changing the asset class: reuses [[time-series-momentum]]
exactly as validated on [[tsmom-spy-qqq]] (Sharpe 0.813, this vault's
joint-best single-leg result), applied to a small, liquid, 24/7 crypto
universe instead of SPY/QQQ.

## Hypothesis

[[time-series-momentum]]: BTC/USD and ETH/USD's own trailing 12-month
return, measured with a 1-month skip to net out short-term reversal,
predicts the sign of near-term drift — the identical causal claim
[[tsmom-spy-qqq]] tested, unchanged. Long-only, scored independently per
symbol, exactly as before.

`strategies/tsmom_btc_eth.py` reuses `tsmom_spy_qqq.Signal.generate()`
unmodified (imported directly, not reimplemented) — the only difference
from the equity version is a calendar-unit correction, not a new design
choice: `lookback=252`/`skip=21` are trading-day BAR counts that read as
"12 months / 1 month" only because equities have ~252 sessions/year.
Alpaca's crypto snapshot has a bar for every calendar day (24/7 spot
trading, confirmed zero weekend/holiday gaps — 1461 bars over exactly 4
calendar years), so reusing the literal integers 252/21 unchanged would
silently shrink the window to ~8.3 calendar months skipping ~3 weeks — a
*different* signal than the one already validated, not the same
mechanism carried over. `lookback=365`, `skip=30` preserve the actual
"trailing 12 months, skip the most recent month" construction. Fixed at
these calendar-equivalent values before any backtest ran, not searched.
Risk parameters (`max_position_pct=5.0`, `stop_loss_pct=2.0`,
`stop_loss_cooldown_sessions=10`) carried over unchanged from
[[tsmom-spy-qqq]] for comparability, per the same discipline as every
other single-variable follow-up in this vault.

`folds=8` is likewise fixed before running, not searched: `wf_sharpe`/
`wf_sortino` are the mean of per-fold annualized Sharpes, so fold count
is a real methodological choice, not a cosmetic reporting detail.
[[tsmom-spy-qqq]] used `folds=12` over 2263 aligned equity sessions
(~189 sessions/fold). Reusing `folds=12` unchanged on this snapshot's
1461 sessions would shrink each fold to ~122 sessions, a noisier
per-fold estimate than the equity precedent used. `folds=8` matches
per-fold sample size instead (~183 sessions/fold, closest integer match
to ~189) — matching statistical power per fold, the more relevant
comparison than matching fold *count* or calendar time.

**Killed if:** walk-forward Sharpe (2021-01-01 to 2024-12-31, the full
pinned crypto snapshot, `folds=8`, 5 bps fees + 5 bps slippage) fails to
clear the **standing** `backtest_to_paper` gate — Sharpe ≥1.0, Sortino ≥1.2,
`contracts/promotion_thresholds.toml` as currently set. Not a
hypothetical adjusted gate: the human explicitly declined to loosen this
threshold for [[tsmom-ms-shift-blend]] specifically because it's written
into that strategy's own pre-registered kill criterion, and lowering it
after the fact to rescue a result would undermine the discipline that
retired the other 12 equity strategies cleanly. The same bar applies
here. **Also killed** (mechanism-level, not just a near-miss) if the
strategy is *in* the market through the acute November 2022 FTX-collapse
shock (a within-lookback-window crash the signal is mechanically blind
to, same structural blind spot [[tsmom-spy-qqq]]'s falsification test
already found for COVID) rather than flat through the slower 2022 bear
decline that preceded it — the same asymmetric-protection signature
already established on equities, expected to replicate here if the
mechanism, not the asset class, is what's driving it.

## Mechanism

No new causal claim: see [[time-series-momentum]] and
[[tsmom-spy-qqq]]'s own Mechanism section — underreaction to slowly
impounded information plus trend-following flows mechanically reinforcing
a move once underway. The only open question this page adds is whether
that mechanism transfers to a market with different participants
(retail- and momentum-fund-heavy rather than institutional-rebalancing-
heavy), different liquidity/vol regime, and no overnight-gap structure
(continuous 24/7 trading means no weekend gap risk the equity version's
stop-loss/re-arm logic had to account for).

## Falsification test

Same structure as [[tsmom-spy-qqq]]'s: check flat-fraction of the raw
(pre-stop-loss) signal during two known drawdown windows, not just the
aggregate Sharpe. The 2022 crypto bear market ran roughly 2021-11-10
(BTC's cycle ATH, ~$69k) to 2022-11-21 (post-FTX trough, ~$15.6k) — a
slow, ~12-month grind trailing momentum should substantially sit out, the
same shape as tsmom-spy-qqq's 2022 equity bear result (48–52% flat). The
FTX-collapse acute crash (2022-11-06 to 2022-11-14, BTC down roughly 25%
in a single week) is a fast, within-lookback-window shock the signal is
mechanically blind to by construction — expected fully-invested (0% flat)
on the same logic as the COVID-crash result, not evidence the signal is
broken if that triggers.

## Manifest

```strategy_manifest
{
  "schema_version": "1.0.0",
  "id": "tsmom-btc-eth",
  "wiki_page": "brain/wiki/strategies/tsmom-btc-eth.md",
  "market": "crypto",
  "family": "swing",
  "universe": ["BTC/USD", "ETH/USD"],
  "hypothesis": "BTC/USD and ETH/USD's own trailing 12-month return (skipping the most recent month, calendar-day-adjusted lookback=365/skip=30 to preserve the same construction tsmom-spy-qqq validated on trading-day bars) predicts the sign of near-term drift; long-only, scored independently per symbol. Killed if walk-forward Sharpe does not clear the standing 1.0/1.2 gate, or if the strategy is long (not flat) through the November 2022 FTX-collapse shock while also failing to sit out the slower 2022 bear decline.",
  "signal_spec": { "language": "python", "entrypoint": "strategies/tsmom_btc_eth.py:Signal" },
  "risk": { "max_position_pct": 5.0, "stop_loss_pct": 2.0, "stop_loss_cooldown_sessions": 10 },
  "lifecycle": "retired",
  "scorecard": {
    "sharpe_wf": 0.21921, "sortino_wf": 0.478232, "max_drawdown_bt": 3.680552,
    "sharpe_paper": null, "max_drawdown_paper": null, "pnl_live": null,
    "rank": null
  }
}
```

## Evidence

Real walk-forward backtest (2021-01-01 to 2024-12-31, `folds=8`, real
BTC/USD+ETH/USD Alpaca crypto data, `data/results/tsmom-btc-eth/`):
**Sharpe 0.21921, Sortino 0.478232, max drawdown 3.680552%, turnover
0.76819.** A clear miss, not a near-miss — well below both the standing
1.0/1.2 gate and well below [[tsmom-spy-qqq]]'s own 0.813366/1.216489 on
the identical mechanism on equities. Fold Sharpes:
`[0.0, 0.0, -1.417, 0.0, -0.689, 1.249, 1.63, 0.981]` — three of eight
folds are exactly flat (zero variance, no open position for that entire
window), a much choppier profile than tsmom-spy-qqq's one weak fold out
of twelve. Turnover (0.768) is 65% higher than tsmom-spy-qqq's (0.465)
despite an identical no-state-machine signal — more whipsaw on this
asset class at this lookback, not fewer decisions.

OOS holdout (trailing 25%, split 2024-01-02): in-sample Sharpe 0.059486,
OOS Sharpe 1.293615 — a large apparent improvement, but not read as a
strong non-overfit signal the way tsmom-spy-qqq's OOS pass was: the
trailing 25% here is only ~365 days on a 4-year total window (vs.
tsmom-spy-qqq's 9-year window), and it happens to land almost entirely on
2024, crypto's strongest bull year in this sample. A near-zero in-sample
Sharpe jumping to 1.29 on one specific bull-market year is a small-sample,
regime-dependent result, not a validated robustness finding — flagged
explicitly rather than counted as supporting evidence, unlike
tsmom-spy-qqq's OOS pass which spanned a much longer, more regime-mixed
holdout.

Falsification check (raw signal, `scripts/tsmom_btc_eth_backtest.py`):
during the slow 2021-11-10 to 2022-11-21 bear decline, the strategy was
flat 90.2% of sessions on BTC/USD and 68.4% on ETH/USD — sat out the slow
grind as the mechanism predicts, comparable to tsmom-spy-qqq's 48–52%
flat during the 2022 equity bear. During the acute 2022-11-06 to
2022-11-14 FTX-collapse shock, the strategy was **flat 100%** of
sessions on both symbols — **the pre-registered kill condition here did
NOT trigger**, unlike tsmom-spy-qqq's COVID result (0% flat, fully
invested through the shock). The difference is explained, not
coincidental: crypto had already been in a sustained downtrend since
November 2021, so trailing 12-month momentum was already deeply negative
and the position already flat by the time the FTX shock hit in November
2022 — there was no abrupt reversal from strongly-positive trailing
momentum the way equities had going into February 2020. This is a
genuine, informative difference in market structure (a shock arriving
mid-drawdown vs. a shock arriving at a trend peak), not evidence the
mechanism behaves differently by asset class.

Additional diagnostics run for context: BTC/USD and ETH/USD's own daily
return correlation is 0.811 (high — limited diversification benefit from
trading both rather than one), and the raw signal agrees (same
long/flat state) on 92.3% of sessions — the two legs are not
meaningfully independent bets here, closer to one redundant signal
traded twice than two genuinely distinct ones. Both symbols spent the
majority of the sample flat (60.6% BTC, 55.0% ETH) — this construction
sits out more than it's invested, on both the count of raw flat-time and
the zero-variance folds above.

**Reading the result:** the mechanism itself replicated faithfully — the
same asymmetric protection pattern (catches slow bear grinds, blind to
in-window shocks) shows up on crypto exactly as it did on equities, and
in fact avoided the specific shock this page pre-registered as a kill
trigger. But the aggregate Sharpe is a clear miss, not a near-miss like
every prior tsmom-family result in this vault, driven by three flat
folds and turnover 65% higher than the equity baseline on an identical
signal. This is evidence against the "the universe was the ceiling"
hypothesis in its simplest form — moving to a structurally different
24/7 asset class did not by itself unlock a materially better result for
this specific mechanism; if anything it performed worse than the
equity-universe ceiling this campaign set out to test past.

## Lifecycle history

- 2026-07-22 — created at `research` — first strategy in this vault on a
  non-`us_equities` market, direct test of whether the Sharpe ~0.6–0.9
  ceiling found across 13 equity-universe strategies is a property of
  the data/universe rather than of mechanism design. Reuses
  [[time-series-momentum]]/[[tsmom-spy-qqq]]'s signal unmodified, with
  lookback/skip converted from trading-day to calendar-day units
  (365/30) to preserve the same 12-1-month construction on a 24/7
  market; risk parameters carried over unchanged. Both the standing
  1.0/1.2 gate and the FTX-collapse/2022-bear falsification test fixed
  before any backtest ran. Required a small contracts/engine patch
  first (`market: "crypto"` added to the manifest schema; per-market
  annualization in `backtest/engine.py`/`oos.py`, 365 sessions/year for
  crypto vs. equities' 252) — see that commit for detail; 146/146
  existing tests passed unchanged before and after. index.md updated.
- 2026-07-22 — retired — Sharpe 0.21921, Sortino 0.478232, a clear miss
  (not a near-miss), well below both the 1.0/1.2 gate and
  tsmom-spy-qqq's own 0.813366/1.216489 on the identical mechanism on
  equities. The pre-registered falsification test did NOT trigger — the
  strategy was flat 100% through the FTX-collapse shock (already
  de-risked from the preceding slow bear decline, unlike tsmom-spy-qqq's
  COVID result) — so the mechanism's asymmetric-protection signature
  replicated faithfully on crypto; the failure is purely on aggregate
  Sharpe, driven by three flat folds (of 8) and turnover 65% higher than
  the equity baseline on an unchanged signal. BTC/USD and ETH/USD's
  return correlation (0.811) and raw signal agreement (92.3%) mean this
  wasn't really two independent bets. OOS holdout shows a large
  in-sample-to-OOS Sharpe jump (0.059 to 1.294) but is explicitly NOT
  read as a robust non-overfit signature the way tsmom-spy-qqq's was —
  the trailing-25% OOS window here is only ~1 year on a 4-year total
  sample and lands almost entirely on 2024's crypto bull run, a
  small-sample regime effect, not validated robustness. Net reading:
  evidence AGAINST the simple "the equity universe was the ceiling, a
  different asset class unlocks a better result" hypothesis — moving to
  a structurally different 24/7 market did not by itself help this
  mechanism, and in fact underperformed the equity-universe ceiling this
  test set out to check. Not a parameter-tuning target: lookback/skip
  calendar-conversion and folds=8 were both fixed before this backtest
  ran and stay that way. See [[research-campaign-2026-07-21]] and
  [[pinned-universe-diversity-2026-07-22]] for the equity-side context
  this result responds to.
