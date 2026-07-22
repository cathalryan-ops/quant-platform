---
type: postmortem
created: 2026-07-22
---

# Overnight return effect — decomposition analysis — SPY/QQQ 2016-2024

Quantify, don't narrate. **Not a gated walk-forward backtest** — see
[[overnight-return-effect]] for why `engine.py`'s close-price-only
execution model cannot express an intraday-vs-overnight position split,
and why this is a direct return-decomposition analysis of the pinned
SPY/QQQ snapshot's own open/close columns instead
(`sandbox/backtest/scripts/overnight_return_decomposition.py`, no
manifest/`run_backtest` path, no `data/results/` entry).

## Result: the split is real and directionally as the literature predicts

| Symbol | Leg | Ann. return | Ann. vol | Sharpe |
|---|---|---|---|---|
| SPY | overnight | 7.37% | 11.53% | 0.675 |
| SPY | intraday | 5.00% | 13.00% | 0.440 |
| SPY | total (buy & hold) | 12.71% | 17.61% | 0.768 |
| QQQ | overnight | 10.95% | 13.42% | 0.842 |
| QQQ | intraday | 7.12% | 17.25% | 0.485 |
| QQQ | total (buy & hold) | 18.84% | 22.22% | 0.889 |

Overnight Sharpe clears intraday Sharpe on both symbols (lower vol,
comparable-to-better return) — reproduces the Cliff/Cooper/Gulen /
Lou-Polk-Skouras direction. It does **not** reproduce the more extreme
"tug of war" version some samples show (negative intraday return):
intraday is weaker but still clearly positive on both symbols here,
consistent with this vault's recurring finding elsewhere ([[low-vol-anomaly-2026-07-22]],
[[pinned-universe-diversity-2026-07-22]]) that 2016-2024 is a
persistently long-biased window — even the "losing" leg of a
return decomposition still comes out positive.

## The real finding: not tradeable at daily granularity under this vault's cost model

The mechanism requires a full round trip **every single session** (buy
at close, sell at next open, no way to reduce trade frequency without
abandoning the "overnight only" construction itself — unlike every
prior strategy in this vault, this is not a parameter that can be
loosened). At this vault's standard cost assumption (5bps fee + 5bps
slippage, each way = 20bps round-trip/session, same `FEE_PCT`/
`SLIPPAGE_BPS` constants every other strategy here is charged):

| Symbol | Gross overnight ann. return | Net of 20bps/session | Net Sharpe |
|---|---|---|---|
| SPY | 7.37% | **-35.16%** | -3.697 |
| QQQ | 10.95% | **-33.00%** | -2.914 |

The average daily overnight edge is a few basis points; the standing
cost model charges 20bps every session regardless. This isn't a
near-miss or a fitted-parameter problem — it's a structural mismatch
between the mechanism's required trading frequency and this vault's
cost assumptions, roughly an order of magnitude apart. No parameter in
this construction (lookback, threshold, universe) changes that ratio.

## Verdict & follow-ups

**Not registered as a strategy** — no manifest was written, nothing to
retire against the 1.0/1.2 gate, because there is no way to express this
mechanism through `run_backtest` without either bending the engine to
mis-price it or fabricating a costless/frictionless version inconsistent
with every other result in this vault. The effect itself replicates
directionally in this sample; the finding is that it's uneconomic here
at daily granularity, not that it's false.

Candidate follow-ups, not attempted here: (a) a genuine engine extension
supporting intra-session open-vs-close position timing (nontrivial —
touches the core `vbt.Portfolio.from_orders` construction every existing
result depends on; would need the same byte-identical-reproduction
scrutiny the short-position extension for [[pairs-trading-stocks50]] got);
(b) test whether the overnight edge is concentrated in a
subset of sessions (e.g. post-earnings, FOMC days) with better forward
carry-adjusted economics than every session; (c) test on the 50-stock
universe for a cross-sectional confirmation (not done here — kept to the
single-asset SPY/QQQ case every other single-asset mechanism in this
vault was first tested on, per the same-comparability convention).

## Cross-mechanism pattern across today's "new mechanism class" sweep

Four structurally distinct, non-momentum mechanisms were tested today:
[[low-volatility-anomaly]] (Sharpe 0.519, best cross-sectional result to
date, but inverts its own risk-reduction premise), pairs-trading /
[[pairs-trading-stat-arb]] (Sharpe -0.540, this vault's first negative
result, spurious full-sample cointegration), and this overnight-effect
analysis (directionally real, structurally uneconomic at this vault's
cost model). None cleared the gate; none failed for the same reason
(inverted premise, false-positive screen, cost-structure mismatch — three
different failure modes, not one repeated one). Combined with
[[universe-scale-2026-07-22]] closing the wider-universe lever the same
day, every mechanism-design and universe-design lever raised by the
2026-07-21/22 research campaign and its Telegram digests has now been
tested at least once. Flagged for the next research pass, not decided
here: whether to keep searching mechanism space (candidates above) or
pause backtest-only research on these fixed 2016-2024/2021-2024 windows.

## Links

- Concept: [[overnight-return-effect]]
- Script: `sandbox/backtest/scripts/overnight_return_decomposition.py`
- Data: `data/us_equities/daily/QQQ_SPY_2016-01-01_2024-12-31.parquet`
  (existing pinned snapshot, no new fetch)
