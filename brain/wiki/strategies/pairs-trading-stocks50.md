---
type: strategy
created: 2026-07-22
---

# Pairs Trading / Stat-Arb — 50 Single-Name Stocks

First long-short strategy in this vault, and the first test of
[[pairs-trading-stat-arb]] — relative-value mean-reversion of the spread
between two cointegrated same-sector stocks, market-neutral by
construction, structurally distinct from every prior mechanism here
(time-series/cross-sectional momentum, market-structure-shift,
single-asset mean-reversion, calendar, low-volatility anomaly). Reuses
the pinned 50-single-name-stock universe (`sandbox/backtest/DATA.md`) —
no new data fetch.

## Pair screen (pre-registered before any backtest ran)

Screened same-sector pairs only (11 GICS sectors, all `C(n,2)` pairs
within each of the 50-stock universe's 11 sector groups — cross-sector
pairs were never in scope: the economic rationale for two names sharing
a long-run price relationship is that they compete for the same demand,
which same-sector names do and cross-sector names generally don't).
Engle-Granger cointegration test (`statsmodels.tsa.stattools.coint`) on
full-sample (2016-2024) daily closes, threshold **p < 0.05 fixed before
looking at any result**. Four pairs cleared it: JNJ/ABT (p=0.0186),
CVX/COP (p=0.0262), DUK/SO (p=0.0280), JPM/AXP (p=0.0317, dropped for
tractability — a flagged follow-up, not cherry-picked among failures).
The three strongest by p-value are traded: **JNJ/ABT, CVX/COP, DUK/SO**.

## Hypothesis

For each of the three pairs, a 60-day rolling OLS hedge ratio
(`Cov(A,B)/Var(B)`) forms a spread `A - beta*B`; when its 60-day z-score
exceeds ±2.0, go long the cheap leg / short the rich leg
(hedge-ratio-weighted), exit at |z| ≤ 0.5 (converged) or after 20 sessions
(safety exit). If the pairs are genuinely cointegrated, the spread should
mean-revert reliably enough to clear costs — market-neutral, so this
tests a return source independent of overall market direction, unlike
every prior strategy here.

Parameters fixed before any backtest ran: `hedge_lookback=zscore_lookback=60`
(~1 quarter — shorter than every momentum lookback in this vault, 252
days, by design: a relationship stat-arb needs to track responsively,
not an annual trend; the closest published analogue at this horizon is
Gatev/Goetzmann/Rouwenhorst's 6-month trading period). `entry_z=2.0`,
`exit_z=0.5` — the standard two-sigma-entry/half-sigma-exit thresholds
from the pairs-trading literature. `max_hold_days=20` (~1 month) — a
safety exit against a relationship that stops reverting, not a tuning
target; re-arm-gated (see `strategies/pairs_trading_stocks50.py`) so a
max-hold exit can't instantly re-trigger into the same unconverged
spread. `beta_min=0.1`/`beta_max=3.0` — a numerical-stability clip on the
rolling hedge ratio, not a tuning target (the three pairs' full-sample
betas are all 0.6-0.9, comfortably inside it).

**Killed if:** walk-forward Sharpe (2016-2024, 12 folds, 5 bps fees + 5
bps slippage) fails to clear the standing gate (Sharpe ≥1.0, Sortino
≥1.2). **Also checked:** does each pair's spread actually converge
reliably (exit-via-z vs. exit-via-max-hold-timeout ratio), and is the
cointegration stable across the sample or does it weaken in the second
half (a classic false-edge trap for stat-arb)?

## Mechanism

See [[pairs-trading-stat-arb]]. Temporary supply/demand imbalances or
liquidity shocks push two structurally linked names' prices apart;
convergence trading harvests the reversion of the spread itself, not
either asset's own price level reverting — structurally distinct from
[[mean-reversion-spy-qqq]] (already a confirmed mechanism-level null,
Sharpe 0.023), which is absolute single-asset reversion. Also the first
market-neutral construction in this vault: every prior cross-sectional
strategy ([[cross-sectional-momentum-stocks50]], [[low-volatility-anomaly]])
is long-only.

## Falsification test

Run directly in `scripts/pairs_trading_stocks50_backtest.py`, per pair:

1. **Convergence vs. timeout** — of all completed trades, what fraction
   exited because the spread actually converged (|z| ≤ 0.5) vs. because
   `max_hold_days` was hit without convergence? A pair that mostly times
   out isn't really mean-reverting on this signal's horizon.
2. **Cointegration stability** — re-run the Engle-Granger test separately
   on the first half and second half of the 2016-2024 sample. A pair
   whose cointegration is strong in one half and weak/absent in the
   other has a relationship that isn't stationary across the full
   window — the classic stat-arb false-edge trap this check exists to
   catch.

## Manifest

```strategy_manifest
{
  "schema_version": "1.0.0",
  "id": "pairs-trading-stocks50",
  "wiki_page": "brain/wiki/strategies/pairs-trading-stocks50.md",
  "market": "us_equities",
  "family": "swing",
  "universe": ["ABT", "AXP", "COP", "CVX", "DUK", "JNJ", "SO"],
  "hypothesis": "Three same-sector pairs (JNJ/ABT, CVX/COP, DUK/SO) pre-registered via Engle-Granger cointegration (p<0.05 on the full 2016-2024 sample) trade a 60-day rolling-hedge-ratio spread: long the cheap leg / short the rich leg when the spread's z-score exceeds +/-2.0, exit at |z|<=0.5 or after a 20-session safety timeout. First long-short, market-neutral mechanism in this vault -- killed if walk-forward Sharpe does not clear 1.0, or if the pairs mostly time out rather than converge, or if cointegration is unstable across the sample's two halves.",
  "signal_spec": { "language": "python", "entrypoint": "strategies/pairs_trading_stocks50.py:Signal" },
  "risk": { "max_position_pct": 5.0, "stop_loss_pct": 4.0, "stop_loss_cooldown_sessions": 10 },
  "lifecycle": "retired",
  "scorecard": {
    "sharpe_wf": -0.539613, "sortino_wf": -0.511119, "max_drawdown_bt": 4.62382,
    "sharpe_paper": null, "max_drawdown_paper": null, "pnl_live": null,
    "rank": null
  }
}
```

Note: `universe` lists only the 6 symbols actually traded (JPM/AXP was
screened but dropped, see the pair screen above — AXP appears because
JPM/AXP was one candidate; JPM itself is not traded so it is correctly
excluded here). `stop_loss_pct=4.0` (vs. every prior strategy's 2.0) —
widened because this signal's own entry threshold (z=2.0 on a 60-day
window) already implies moves in the ~2-4% range are an expected, not
exceptional, part of normal spread divergence before convergence; a 2%
stop would risk clipping entries on their own expected noise band rather
than a genuine breakdown. Not re-derived from this backtest's result.

## Evidence

Real walk-forward backtest (2016-01-01 to 2024-12-31, `folds=12`, real
50-stock Alpaca data, split-adjusted, reusing the pinned
`cross-sectional-momentum-stocks50` snapshot,
`data/results/pairs-trading-stocks50/`): Sharpe **-0.539613**, Sortino
-0.511119, max drawdown 4.62%, turnover 2.269397 — not just a gate miss
but this vault's first strategy with a **negative** walk-forward Sharpe.
Fold Sharpes: `[-2.491, -0.757, -1.406, -0.686, 1.233, 0.908, -0.553,
-0.871, -0.009, 1.517, -1.564, -1.798]` — 8 of 12 folds negative. OOS
holdout rejected outright: in-sample Sharpe already <= 0 (-0.123), so the
OOS comparison isn't even meaningful.

Falsification check 1 (convergence vs. timeout) — **the mechanism mostly
doesn't converge**: JNJ/ABT 17.9% converged (23 of 28 trades timed out),
CVX/COP 21.2% converged, DUK/SO 24.1% converged. All three pairs spend
the large majority of trades riding to the 20-session safety exit rather
than reverting, directly contradicting the hypothesis's core claim.

Falsification check 2 (**the decisive finding**) — cointegration is not
stable across the sample, and in fact barely existed outside the
full-sample regression: re-running Engle-Granger separately on the first
half (2016-2020) and second half (2020-2024) of the data:

| Pair | Full-sample p | First-half p | Second-half p |
|---|---|---|---|
| JNJ/ABT | 0.0186 | 0.0382 | 0.2469 |
| CVX/COP | 0.0262 | 0.1283 | 0.2628 |
| DUK/SO | 0.0280 | 0.3036 | 0.3327 |

**None of the three pairs clear p<0.05 in the second half; two of three
don't clear it in the first half either.** The full-sample significance
that passed the pre-registered screen looks like an artifact of shared
long-run upward drift across a 9-year bull-biased window (both legs of
each pair are large, quality, dividend-paying names that broadly rose
together over 2016-2024) rather than genuine short-horizon mean-reverting
co-integration — a classic spurious-regression trap for Engle-Granger on
trending series, and exactly the failure mode the screen's own
first/second-half check exists to catch. See
[[pairs-trading-stocks50-2026-07-22]] for the full writeup and what it
implies for any future cointegration screen in this vault.

## Lifecycle history

- 2026-07-22 — created at `research` — first long-short, market-neutral
  mechanism in this vault, direct response to the "new mechanism class"
  lever (after [[universe-scale-2026-07-22]] and
  [[blend-leg-search-2026-07-22]] both closed, and
  [[low-vol-anomaly-2026-07-22]] closed low-vol specifically while
  leaving pairs/stat-arb and overnight-effect flagged as untried).
  Required extending `backtest/risk.py`'s stop-loss overlay and
  `backtest/signal.py`'s weight-bound check to support short positions
  (both previously long-only-only by omission, not design — no strategy
  before this one ever produced a negative weight); both changes are
  additive and verified not to change any existing strategy's output
  (202/202 tests pass, including 6 new short-side risk tests). Pairs
  screened via Engle-Granger cointegration on the full sample with a
  pre-registered p<0.05 threshold before any backtest ran.
- 2026-07-22 — retired — Sharpe -0.539613, this vault's first *negative*
  walk-forward result. Both falsification checks explain why: trades
  mostly time out rather than converge (17.9%-24.1% convergence rate
  across the three pairs), and re-running the cointegration screen on
  each half of the sample separately shows none of the three pairs hold
  up in the second half (p=0.25-0.33) — the full-sample significance was
  most likely shared long-run drift, not real short-horizon
  mean-reversion. Not a parameter-tuning target (hedge_lookback,
  zscore_lookback, entry_z, exit_z, max_hold_days, beta clip all fixed a
  priori for the reasons stated above and stay fixed). See
  [[pairs-trading-stocks50-2026-07-22]] for the methodological
  implication for future cointegration screens in this vault.
