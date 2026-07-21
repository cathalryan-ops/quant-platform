---
type: postmortem
created: 2026-07-21
---

# Backtest-only research campaign — 2026-07-21

> Cross-strategy synthesis, not a single paper/live review — every strategy
> proposed and retired in this vault to date is backtest-only (no strategy
> has reached `paper`), so there is no realised-vs-expected delta to
> report yet. This page exists instead to ask: after 12 genuinely distinct
> mechanisms, all retired, is there a shared reason nothing has cleared the
> backtest→paper gate, and what does that imply for what to try next?

Quantify, don't narrate.

## Every result, ranked

All real walk-forward backtests, 2016-01-01 to 2024-12-31, 12 folds, 5 bps
fees + 5 bps slippage, against the standing gate (`sharpe_wf` ≥1.0,
`sortino_wf` ≥1.2, `contracts/promotion_thresholds.toml`). **All 12 failed
`passed_thresholds`.**

| Strategy | Mechanism class | Sharpe | Sortino | Max DD % | Turnover | Verdict |
|---|---|---|---|---|---|---|
| [[tsmom-spy-qqq]] | absolute momentum | 0.813 | 1.216 | 2.305 | 0.465 | near-miss, zero fit params |
| [[ms-shift-spy-high-displacement]] | day-scale structure break | 0.813 | 1.200 | 1.180 | 0.186 | near-miss, one fit param |
| [[tsmom-vol-target]] | absolute momentum + continuous vol gate | 0.742 | 1.093 | 1.697 | 0.496 | worse than ungated |
| [[ms-shift-spy]] | day-scale structure break | 0.674 | 0.963 | 1.435 | 0.367 | miss |
| [[52wk-high-spy-qqq]] | anchoring bias | 0.625 | 1.052 | 2.256 | 1.056 | miss, ~80% correlated with tsmom |
| [[tsmom-vol-accel-hysteresis]] | absolute momentum + hysteresis vol gate | 0.608 | 0.967 | 1.745 | 0.992 | worse than ungated |
| [[tsmom-breadth-gate]] | absolute momentum + cross-sectional breadth gate | 0.559 | 0.807 | 2.290 | 0.749 | worse than ungated |
| [[tsmom-vol-accel]] | absolute momentum + binary vol gate | 0.534 | 0.872 | 1.878 | 1.146 | worse than ungated |
| [[sector-rotation]] | cross-sectional momentum | 0.255 | 0.391 | 3.130 | 1.524 | clear miss, XLK-concentrated |
| [[ms-shift-spy-vol-regime]] | day-scale structure break + absolute vol band | 0.120 | 0.315 | 0.786 | 0.457 | worse than ungated |
| [[dual-momentum-equity-bond-gold]] | cross-sectional + absolute floor | 0.101 | 0.240 | 1.401 | 0.363 | clear miss, mechanism verified real |
| [[mean-reversion-spy-qqq]] | day-scale mean reversion | 0.023 | 0.356 | 2.597 | 1.702 | clean null |
| [[turn-of-month-spy-qqq]] | calendar | 0.022 | 0.303 | 1.325 | 2.393 | clean null |

(`sma-cross-demo` excluded — integration-test scaffold, not a research
hypothesis.)

## Patterns across the campaign

**1. The best two results are a tie, from unrelated mechanisms, both ~19%
short.** [[tsmom-spy-qqq]] (month-scale absolute momentum, zero fit
parameters) and [[ms-shift-spy-high-displacement]] (day-scale structure
break, one fit parameter) both land at Sharpe 0.813 — structurally
unrelated signal types, different horizons, independently arriving at
the same ceiling. Neither is a fitted result chasing this specific number;
that convergence is itself informative about where this data/window's
risk-adjusted opportunity set tops out for a long-only directional bet.

**2. Every attempt to filter tsmom-spy-qqq made it worse, not better —
three separate times, three structurally different filter types.**
[[volatility-acceleration]] (self-referential, binary), volatility
hysteresis (same, with a re-entry gap), [[volatility-targeting]]
(self-referential, continuous), and [[market-breadth]] (cross-sectional,
binary) all reduced Sharpe versus the ungated baseline, every time via
turnover/whipsaw cost exceeding whatever drawdown protection the filter
bought. This is now a strong pattern, not a single result: the
ungated tsmom-spy-qqq construction looks like a local optimum for this
specific edge on this data, and further "add a smarter gate" ideas on
this exact signal are a low-probability use of research budget going
forward.

**3. Cross-sectional strategies underperform the absolute-momentum
baseline, and both flag the same limiting factor.** [[sector-rotation]]
and [[dual-momentum-equity-bond-gold]] each verified their own mechanism
worked as designed (genuine rotation, genuine cash floor) but both landed
well below [[tsmom-spy-qqq]], and both independently flagged the same
next step: the pinned universe (10 sectors, 3-asset cross-asset basket)
is too narrow to give cross-sectional momentum a fair test — this reads
as a data-scale ceiling, not a mechanism-design failure.

**4. Two mechanisms are clean, unambiguous nulls on this data.**
[[mean-reversion-spy-qqq]] and [[turn-of-month-spy-qqq]] both landed at
Sharpe ≈0.02 with no falsification-test support either — genuinely absent
effects on this sample, not near-misses. Worth remembering as closed
questions if new data ever makes revisiting them cheap, but not worth
further budget on this data.

## Verdict & follow-ups

No strategy here is a modelling error or an execution surprise (there is
no paper/live session yet to compare against) — this is a pure
research-yield read: 12 genuinely distinct mechanisms, systematically
covering day-scale/month-scale, absolute/cross-sectional, and
single-asset/multi-asset-class constructions, and the ceiling on this
exact 2016-2024 SPY/QQQ/sector data is ~0.81 Sharpe, about 19% short of
the backtest→paper gate. Two concrete follow-ups:

- **Flag the gate itself for human review.** `contracts/promotion_thresholds.toml`
  is read-only to agents per the root constitution; this vault cannot loosen
  it, only note the finding. Worth a Telegram flag: is `min_walkforward_sharpe
  = 1.0` calibrated to what a real edge looks like on long-only daily-bar
  US equity/sector data over this specific window, given the two best
  structurally-independent, non-overfit ideas both landed at 0.813?
- **The one combination never tried: blend tsmom-spy-qqq with
  ms-shift-spy-high-displacement instead of gating either one alone.**
  Every gating attempt so far has applied a FILTER to tsmom (multiply its
  weight by 0/1) rather than combined it with a second, structurally
  independent EDGE. The two best results are different signal types at
  different horizons (month-scale trend vs. day-scale structure break) —
  if their return streams are meaningfully uncorrelated, a blend could
  reduce variance disproportionately to any return given up, which is
  exactly the lever gating never had access to (gating only ever removes
  exposure, it can't add a second, differently-timed source of edge).
  Untested; the natural next hypothesis if research continues on this
  data before waiting on a universe expansion.

## Links

- Strategies reviewed: [[tsmom-spy-qqq]], [[ms-shift-spy-high-displacement]],
  [[tsmom-vol-target]], [[ms-shift-spy]], [[52wk-high-spy-qqq]],
  [[tsmom-vol-accel-hysteresis]], [[tsmom-breadth-gate]], [[tsmom-vol-accel]],
  [[sector-rotation]], [[ms-shift-spy-vol-regime]],
  [[dual-momentum-equity-bond-gold]], [[mean-reversion-spy-qqq]],
  [[turn-of-month-spy-qqq]]
- Concepts: [[time-series-momentum]], [[market-structure-shift]],
  [[displacement]], [[cross-sectional-momentum]], [[dual-momentum]],
  [[market-breadth]], [[volatility-acceleration]], [[volatility-targeting]]
- Results: `data/results/<strategy-id>/backtest_result.json` for each
  strategy above
- Thresholds: `contracts/promotion_thresholds.toml`
