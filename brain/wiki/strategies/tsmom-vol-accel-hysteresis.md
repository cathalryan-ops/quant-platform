---
type: strategy
created: 2026-07-21
---

# Time-Series Momentum — Volatility-Acceleration Gate with Hysteresis

A single-variable follow-up to [[tsmom-vol-accel]], same discipline as
every step in this line: reuse the base signal unchanged, add exactly one
independent gate. [[tsmom-vol-accel]] confirmed its own mechanism claim
(COVID-window flat time rose from 0% to ~47%, exactly as designed) but
made aggregate performance worse, not better, because turnover more than
doubled (0.465 → 1.146) — the single-threshold gate chatters on ordinary
volatile-but-not-crisis weeks, not just around genuine regime changes.

## Hypothesis

A gate that opens and closes at the same threshold is exactly the
textbook setup for chatter: whenever the vol ratio oscillates near that
one boundary, the gate flips with it, and each flip is a round-trip that
pays fees and slippage. The standard fix is hysteresis — a lower
re-entry threshold than the exit threshold, so a brief dip back under the
exit level isn't enough to reopen the position; the ratio has to fall
meaningfully further first. If this is really what's driving
tsmom-vol-accel's excess turnover, adding a re-entry gap should cut
turnover materially while preserving most or all of the COVID-window
protection (which only needs the gate to *close* fast, not to reopen
fast).

Parameters fixed before any backtest ran: `vol_short_window=5`,
`vol_long_window=63`, `vol_accel_exit_threshold=1.75` — all three
UNCHANGED from [[tsmom-vol-accel]], not re-fit. The one new variable,
`vol_accel_reentry_threshold=1.25`: [[volatility-acceleration]]'s own
page already reasoned that ratios of 1.2-1.4x occur from ordinary
sampling noise even in calm markets, so 1.25 sits at the low end of that
noise band — comfortably below the 1.75 exit level (a real gap, not a
token one), while not being so strict that the gate would stay closed
indefinitely after any real spike. Not fit to this dataset's outcome.

**Killed if:** walk-forward Sharpe fails to clear the standing gate
(Sharpe ≥1.0, Sortino ≥1.2) — same bar as always. **The specific thing
this page exists to test:** does turnover drop materially versus
tsmom-vol-accel's 1.146 while the COVID-window flat-time benefit
(~47%) is substantially preserved? If turnover doesn't meaningfully
drop, hysteresis isn't fixing the problem it was added to fix, regardless
of what happens to the aggregate Sharpe.

## Mechanism

See [[volatility-acceleration]]. No new claim about *why* vol
acceleration should predict anything — the causal story is identical to
[[tsmom-vol-accel]]'s. This page tests an implementation-level fix (does
the gate's own chatter, not the underlying signal, explain why the prior
version underperformed), not a new economic mechanism.

## Falsification test

Direct comparison against tsmom-vol-accel's recorded numbers: turnover
(1.146 baseline) and COVID-window flat time (~47% baseline, vs.
tsmom-spy-qqq's 0.0% pre-gate). Hysteresis is validated only if turnover
drops materially AND COVID-window flat time stays well above
tsmom-spy-qqq's 0%. If turnover barely moves, the chatter wasn't
happening at the exit boundary the way this page assumes. If COVID-window
flat time collapses back toward 0%, the re-entry threshold is too loose
(reopening the position too eagerly even during the crash itself).

## Manifest

```strategy_manifest
{
  "schema_version": "1.0.0",
  "id": "tsmom-vol-accel-hysteresis",
  "wiki_page": "brain/wiki/strategies/tsmom-vol-accel-hysteresis.md",
  "market": "us_equities",
  "family": "swing",
  "universe": ["SPY", "QQQ"],
  "hypothesis": "tsmom-vol-accel's excess turnover (1.146 vs tsmom-spy-qqq's 0.465) comes from the single-threshold gate chattering near its own boundary on ordinary volatile-but-not-crisis weeks. Adding a lower re-entry threshold (1.25, vs the unchanged 1.75 exit threshold) should cut turnover materially while preserving most of the COVID-window flat-time benefit (~47%). Killed if Sharpe does not clear 1.0, or if turnover does not drop materially, or if COVID-window flat time collapses back toward 0%.",
  "signal_spec": { "language": "python", "entrypoint": "strategies/tsmom_vol_accel_hysteresis.py:Signal" },
  "risk": { "max_position_pct": 5.0, "stop_loss_pct": 2.0, "stop_loss_cooldown_sessions": 10 },
  "lifecycle": "retired",
  "scorecard": {
    "sharpe_wf": 0.607643, "sortino_wf": 0.966973, "max_drawdown_bt": 1.744819,
    "sharpe_paper": null, "max_drawdown_paper": null, "pnl_live": null,
    "rank": null
  }
}
```

## Evidence

Real walk-forward backtest (2016-01-01 to 2024-12-31, `folds=12`, real
SPY+QQQ Alpaca data, `data/results/tsmom-vol-accel-hysteresis/`): Sharpe
0.607643, Sortino 0.966973, max drawdown 1.744819%, turnover 0.992369.
OOS holdout (trailing 25%, split 2022-09-29): in-sample Sharpe 0.710951,
OOS Sharpe 0.847529 — improves on in-sample again, consistent across
every variant in this line. Fold Sharpes: `[0.0, 1.271, 0.93, -0.177,
0.527, 1.578, 1.337, 1.599, -2.835, 1.27, 1.2, 0.591]`.

Falsification check (raw signal, `scripts/tsmom_vol_accel_hysteresis_backtest.py`),
directly against tsmom-vol-accel's recorded numbers:

| window | symbol | hysteresis flat % | vol-accel flat % (no hysteresis) |
|---|---|---|---|
| COVID crash | SPY | 68.6% | 48.6% |
| COVID crash | QQQ | 48.6% | 45.7% |
| 2022 bear market | SPY | 48.0% | 48.0% |
| 2022 bear market | QQQ | 52.0% | 52.0% |

**Directionally confirmed, magnitude insufficient.** Turnover dropped
from 1.146023 to 0.992369 (-13.4%) and both Sharpe (0.534 → 0.608) and
Sortino (0.872 → 0.967) improved, while COVID-window protection was
fully preserved and even *improved* (SPY flat time rose to 68.6%). Every
prediction on this page's own terms came true. But the improvement is
modest, not the "materially" this page's falsification bar called for:
turnover is still more than double [[tsmom-spy-qqq]]'s ungated 0.465489,
and Sharpe/Sortino remain well below both that ungated baseline
(0.813366/1.216489) and the 1.0/1.2 gate. Most of tsmom-vol-accel's
excess turnover was NOT single-threshold chatter after all — it's
mostly real crossings the gate is correctly reacting to, which hysteresis
can only ever trim at the margin, not eliminate.

## Lifecycle history

- 2026-07-21 — created at `research` — single-variable follow-up to
  [[tsmom-vol-accel]], adding one independent re-entry threshold
  (hysteresis) to address that strategy's documented excess-turnover
  problem; vol_accel_reentry_threshold fixed before any backtest run, not
  searched, and exit_threshold/windows carried over unchanged from
  tsmom-vol-accel. Includes `stop_loss_cooldown_sessions: 10` (Option C)
  from the start per [[stop-loss-rearm-coupling]].
- 2026-07-21 — retired — Sharpe 0.607643 / Sortino 0.966973, both still
  far short of the 1.0/1.2 gate and below tsmom-spy-qqq's ungated
  baseline. Every specific prediction this page made came true in
  direction (turnover down 13.4%, Sharpe/Sortino up, COVID-window
  protection preserved and even improved on SPY) but not in magnitude —
  hysteresis was the right lever, but chatter was only ever a minority
  contributor to tsmom-vol-accel's excess turnover, not the dominant one.
  Stopping this specific axis here rather than adding a fourth knob to
  the same binary vol-gate mechanism (widening the re-entry gap further
  would be tuning a result already seen, not testing a new claim). If
  this line gets revisited, the flagged next step is structurally
  different: continuous vol-targeting position sizing (scale exposure
  inversely with realized vol) instead of a binary on/off gate, since a
  hard gate's entire cost structure is the round-trip it forces on every
  crossing, real or not.
