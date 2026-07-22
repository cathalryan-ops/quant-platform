---
type: postmortem
created: 2026-07-22
---

# pairs-trading-stocks50 — backtest — 2016-2024

Quantify, don't narrate.

## Expected vs realised

| Metric | Expected (backtest) | Realised | Delta |
|---|---|---|---|
| Sharpe | ≥1.0 (gate) | -0.539613 | this vault's first negative WF Sharpe |
| Sortino | ≥1.2 (gate) | -0.511119 | — |
| Max drawdown % | ≤15.0 (gate) | 4.62382 | comfortably inside the gate (drawdown was never the problem) |
| Turnover | — | 2.269397 | high — daily hedge-ratio drift plus 76-82% of trades riding to the max-hold exit |

## Root cause: the pre-registered cointegration screen passed on spurious full-sample significance

All three traded pairs (JNJ/ABT, CVX/COP, DUK/SO) cleared the
pre-registered Engle-Granger p<0.05 threshold on the full 2016-2024
sample. Splitting the same test across the first half (2016-01 to
2020-06ish) and second half (2020-06ish to 2024-12) of the identical
data:

| Pair | Full-sample p | First-half p | Second-half p |
|---|---|---|---|
| JNJ/ABT | 0.0186 | 0.0382 | 0.2469 |
| CVX/COP | 0.0262 | 0.1283 | 0.2628 |
| DUK/SO | 0.0280 | 0.3036 | 0.3327 |

Zero of three pairs clear p<0.05 in the second half. Only one
(JNJ/ABT) clears it in the first half, and even that is 2x weaker than
the full-sample number. The full-sample test's apparent significance
almost certainly comes from **shared long-run upward drift** — all six
traded names are large, high-quality, dividend-paying blue chips that
broadly appreciated together over a 9-year bull-biased window — not from
a genuine short-horizon mean-reverting relationship between each pair.
Engle-Granger (like any cointegration test built on OLS residual
stationarity) is known to be vulnerable to exactly this: two trending
series with a roughly stable long-run ratio can look cointegrated over a
long window even when the short-horizon spread this strategy actually
trades doesn't mean-revert on any tradeable timescale.

This is corroborated directly by falsification check 1: only 17.9-24.1%
of completed trades converged via the z-score exit; the large majority
(76-82%) timed out via the 20-session safety exit, meaning the spread
mostly just kept drifting rather than reverting once a position was
open — exactly what "spurious full-sample cointegration, no real
short-horizon reversion" predicts, and exactly why the strategy lost
money net of costs (turnover 2.27, mostly on positions that never
converged).

## Guardrail / execution events

None. `max_drawdown_pct` (4.62%) is well inside the 15% gate — this
result fails on Sharpe/Sortino from a real, if losing, edge, not from a
risk-control breach or an execution/data problem. No KILL, no budget
freeze, no guardrail violation.

## Verdict & follow-ups

**Retired, per the standing 1.0/1.2 gate — and also per the falsification
finding, independent of the gate.** Even if the gate were loosened, this
strategy loses money; it should not be revisited on this pair set without
a methodological fix.

**Reusable finding for any future cointegration screen in this vault**:
a full-sample-only Engle-Granger test on trending equity price levels is
not sufficient evidence of genuine tradeable mean-reversion. A
pre-registered screen should require cointegration to hold up
**separately in multiple non-overlapping sub-periods**, not just on the
full sample — this postmortem's own first/second-half check should
become part of the *screening* methodology next time (pre-registered
alongside the entry threshold), not just a post-hoc falsification check
run after the backtest already failed. Candidate follow-ups, not
attempted here: (a) re-screen with a stability-across-halves requirement
built into the pair selection itself, which would likely have rejected
all three of these pairs before ever writing a Signal; (b) test
sector-index-level pairs (e.g. two sub-sector proxies) instead of
individual stocks, where genuine short-horizon relative-value
relationships are more commonly documented in the literature than
single-name pairs; (c) detrend/demean the spread (e.g. work in returns
or de-drift the price series) before testing cointegration, to separate
shared drift from genuine mean-reversion at the source rather than
after the fact.

## Links

- Strategy: [[pairs-trading-stocks50]]
- Concept: [[pairs-trading-stat-arb]]
- Results: `data/results/pairs-trading-stocks50/backtest_result.json`
