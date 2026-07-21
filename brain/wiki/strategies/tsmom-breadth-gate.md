---
type: strategy
created: 2026-07-21
---

# TSMOM, Sector-Breadth Gated

A third follow-up to [[tsmom-spy-qqq]]'s near-miss (Sharpe 0.813), and the
first gate in that line to use cross-sectional information instead of a
self-referential statistic of the traded asset's own price series. The
vol-gate line ([[volatility-acceleration]] via tsmom-vol-accel /
tsmom-vol-accel-hysteresis, [[volatility-targeting]] via tsmom-vol-target)
all asked "is this asset's own recent behavior getting more violent?" and
all fell short of the ungated baseline. This asks a structurally different
question, only answerable now that the 16-symbol snapshot exists: "is the
broader market backing this trend, or is participation narrowing?"

## Hypothesis

[[market-breadth]]: gate tsmom-spy-qqq's unchanged raw signal off whenever
fewer than `breadth_threshold` (50%, a standard "majority" cut, fixed
before any backtest ran) of the 10 SPDR sector ETFs are themselves in a
positive trailing-12-1-momentum state — even if SPY/QQQ's own trailing
momentum is positive. The claim: a market advance not confirmed by broad
sector participation is more likely to be near an inflection, so filtering
those stretches out should improve risk-adjusted return versus the
ungated baseline, the way vol-acceleration aimed to filter out the specific
case of an accelerating shock (and fell short by widening turnover more
than it saved).

**Killed if:** walk-forward Sharpe (2016-2024, 12 folds, 5 bps fees + 5 bps
slippage) fails to clear the standing gate (Sharpe ≥1.0, Sortino ≥1.2), or
if it doesn't beat tsmom-spy-qqq's ungated 0.813366 baseline. **Also
checked:** does the gate actually bind (spend real time closed) without
being either near-vacuous (breadth is almost always ≥50% when SPY's own
momentum is positive, making it redundant with the base signal) or
near-always-closed (breadth rarely reaches 50%, making this indistinguishable
from staying flat)?

## Mechanism

See [[market-breadth]]. Distinct causal story from the vol-gate line: not
"this specific asset's own move is getting more violent" but "leadership is
narrowing — a shrinking set of sectors is carrying the tape while the rest
lag," historically associated (Zweig Breadth Thrust; advance/decline
divergence literature) with fragile, late-stage rallies more prone to
reversal than broadly-participated ones. Institutionally, narrow leadership
often reflects money crowding into a small number of winners (partly
overlapping with [[cross-sectional-momentum]]'s relative-strength
mechanism) rather than a genuine broad-based expansion in risk appetite.

## Falsification test

Compare the fraction of trading days the gate is closed (breadth <50%)
against the fraction of days SPY/QQQ's own tsmom signal is already flat
(momentum ≤0). If the two are nearly identical, the gate adds nothing
beyond what the base signal already does. If the gate closes on a
materially different, non-trivial set of days (i.e. it fires *while SPY's
own trend is still nominally positive*), it's testing something genuinely
new — whether that improves the result or not is the separate walk-forward
question above.

## Manifest

```strategy_manifest
{
  "schema_version": "1.0.0",
  "id": "tsmom-breadth-gate",
  "wiki_page": "brain/wiki/strategies/tsmom-breadth-gate.md",
  "market": "us_equities",
  "family": "swing",
  "universe": ["SPY", "QQQ", "XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY"],
  "hypothesis": "tsmom-spy-qqq's unchanged signal, gated off whenever fewer than 50% of the 10 SPDR sector ETFs are themselves in a positive trailing-12-1-momentum state, should filter out fragile narrow-leadership stretches and improve on tsmom-spy-qqq's 0.813366 Sharpe. Killed if walk-forward Sharpe does not clear 1.0 or beat the ungated baseline, or if the gate never meaningfully diverges from the base signal's own flat days.",
  "signal_spec": { "language": "python", "entrypoint": "strategies/tsmom_breadth_gate.py:Signal" },
  "risk": { "max_position_pct": 5.0, "stop_loss_pct": 2.0, "stop_loss_cooldown_sessions": 10 },
  "lifecycle": "retired",
  "scorecard": {
    "sharpe_wf": 0.558825, "sortino_wf": 0.806613, "max_drawdown_bt": 2.28975,
    "sharpe_paper": null, "max_drawdown_paper": null, "pnl_live": null,
    "rank": null
  }
}
```

## Evidence

Real walk-forward backtest (2016-01-01 to 2024-12-31, `folds=12`, real
16-symbol Alpaca data, SPY/QQQ traded with the 10 sectors present only as
a breadth source, `data/results/tsmom-breadth-gate/`): Sharpe 0.558825,
Sortino 0.806613 — both a **regression** versus tsmom-spy-qqq's ungated
baseline (0.813366 / 1.216489), a -31.3% and -33.7% relative decline
respectively. Max drawdown 2.28975% is only marginally better than the
ungated baseline's 2.305277% (a 0.7% relative improvement — essentially
noise), while turnover rose to 0.749498, +61.0% over the baseline's
0.465489. Fold Sharpes: `[0.0, 1.446, 1.197, -0.074, 0.948, -0.107, 0.896,
1.771, -1.223, -0.359, 0.94, 1.272]` — four of twelve folds negative. OOS
holdout (trailing 25%, split 2022-09-29): in-sample Sharpe 0.45932, OOS
Sharpe 0.87334 — improves on in-sample (PASSED), the same pattern nearly
every strategy in this vault shows on this particular split.

Falsification check (raw signal,
`scripts/tsmom_breadth_gate_backtest.py`): the gate is not vacuous — it
forces extra flat days beyond what the base tsmom signal alone would have
produced (SPY: base flat 27.3% of days, gated flat 30.8%, gate-caused
3.4%/78 sessions; QQQ: base flat 25.3%, gated flat 30.8%, gate-caused
5.5%/125 sessions) — so this genuinely tested the breadth-confirmation
hypothesis rather than silently reducing to the base signal. But the
result is the same shape as the entire earlier vol-gate line
([[volatility-acceleration]], [[volatility-targeting]]): a real, non-trivial
gate that adds turnover cost exceeding whatever protective value it
provides, netting out worse than the ungated baseline. This is a notable
negative result beyond just "breadth doesn't work" — it's now three
structurally different gate types (self-referential vol-acceleration,
continuous vol-targeting, and now cross-sectional breadth) that have all
made tsmom-spy-qqq's Sharpe worse, not better, which is a meaningfully
stronger claim than any one of them alone: gating this specific signal
with *any* filter tested so far costs more in added turnover/whipsaw than
it saves in avoided drawdown, on this data and window.

## Lifecycle history

- 2026-07-21 — created at `research` — third follow-up gate in the
  tsmom-spy-qqq line, first to use cross-sectional (sector breadth) rather
  than self-referential (own-asset volatility) information; breadth_threshold
  fixed at a standard 50% majority cut before any backtest run, lookback/skip
  carried over unchanged from tsmom-spy-qqq for direct comparability. Includes
  `stop_loss_cooldown_sessions: 10` (Option C) from the start per
  [[stop-loss-rearm-coupling]].
- 2026-07-21 — retired — Sharpe 0.558825 / Sortino 0.806613, a regression
  versus tsmom-spy-qqq's ungated baseline (0.813366 / 1.216489), not an
  improvement as hypothesized. The falsification test passed cleanly — the
  gate genuinely binds on a non-trivial, non-vacuous set of days (78/125
  sessions for SPY/QQQ beyond the base signal's own flat days) — so this is
  a real negative result, not a vacuous one: turnover rose 61.0% while
  drawdown improved only ~0.7% (noise-level), the same turnover-cost-exceeds-
  protection-value shape as the entire earlier vol-gate line. Not a
  parameter-tuning target (breadth_threshold fixed at a standard majority
  cut, not searched); this closes out gating tsmom-spy-qqq as an axis for
  now — three structurally different gate types (self-referential vol,
  continuous vol-targeting, cross-sectional breadth) have all made the
  signal worse, not better, suggesting the ungated construction is close to
  a local optimum for this specific edge on this data rather than any one
  gate's parameterization being the problem.
