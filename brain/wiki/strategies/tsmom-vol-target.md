---
type: strategy
created: 2026-07-21
---

# Time-Series Momentum — Continuous Volatility-Targeted Sizing

A structurally different follow-up to the whole vol-gate line
([[tsmom-vol-accel]], [[tsmom-vol-accel-hysteresis]]), not another knob
on the same mechanism. Both prior variants confirmed that de-risking
during high vol genuinely helps (COVID-window flat time rose from tsmom's
0% baseline in both), but both paid for it with excess turnover from
discrete gate crossings — hysteresis cut that cost by only 13.4% before
the axis was closed. This page replaces the binary gate entirely with a
continuous scaling factor: no threshold, so nothing to chatter across.

## Hypothesis

Instead of forcing the position fully flat when realized vol crosses a
line, continuously scale it down in proportion to how far realized vol
sits above a fixed annualized target — `min(1.0, vol_target /
realized_vol)`, applied on top of [[tsmom-spy-qqq]]'s unchanged 0/1
trend signal. Capped at 1.0 (the base signal's own maximum): the
platform's Signal protocol is long-only/no-leverage in v1, so this can
only ever de-risk relative to the base signal, never lever it up in calm
markets. If most of the vol-gate line's turnover problem really was the
discrete on/off crossing (as tsmom-vol-accel-hysteresis's retirement
suggested, even if only partially), a smooth function of the same
underlying realized-vol signal should reduce risk during shocks with
meaningfully less turnover cost than either binary variant.

Parameters fixed before any backtest ran: `vol_window=20` — the same
standard realized-vol window already used elsewhere in this vault
([[ms-shift-spy-vol-regime]], [[mean-reversion-spy-qqq]]), for internal
consistency rather than picked fresh. `vol_target=0.15` (15% annualized)
— SPY's long-run realized-vol center, already used as the reasoning
anchor in [[ms-shift-spy-vol-regime]]'s page ("SPY's long-run realized
vol center is roughly 15-16% annualized"); reusing that same
already-established, dataset-blind number rather than fitting a new one
to this specific backtest's outcome.

**Killed if:** walk-forward Sharpe fails to clear the standing gate
(Sharpe ≥1.0, Sortino ≥1.2). **The specific thing this page exists to
test:** does turnover come in meaningfully below the vol-gate line's
best result (tsmom-vol-accel-hysteresis's 0.992369) while still
providing real COVID-window protection (materially above
tsmom-spy-qqq's 0%)? If turnover is just as high as the gated variants
despite having no threshold to chatter across, continuous rebalancing
itself — not discrete gate crossings — is the real cost driver, and the
whole vol-scaling direction (not just the gate implementation) is the
wrong lever for this specific problem.

## Mechanism

Same underlying causal story as [[volatility-acceleration]] and
[[ms-shift-spy-vol-regime]]: elevated realized volatility is associated
with regime instability where a slower trend signal's edge is less
reliable, so reducing exposure in proportion to realized vol should trade
off some upside in calm trending periods for materially smaller losses in
volatile ones — the same idea as every vol-targeting overlay used across
CTA/risk-parity strategies, just without this vault's earlier binary
framing of "trade or don't."

## Falsification test

Same falsification harness as the vol-gate line: raw-signal flat/scaled
fraction during the 2020-02-19 to 2020-04-07 COVID crash window and the
2022-01-03 to 2022-10-12 bear market window (reported here as average
position scalar, not a binary flat/long split, since the whole point is
that this signal doesn't binarize). Direct comparison of turnover against
tsmom-vol-accel-hysteresis's recorded 0.992369.

## Manifest

```strategy_manifest
{
  "schema_version": "1.0.0",
  "id": "tsmom-vol-target",
  "wiki_page": "brain/wiki/strategies/tsmom-vol-target.md",
  "market": "us_equities",
  "family": "swing",
  "universe": ["SPY", "QQQ"],
  "hypothesis": "Replacing the vol-gate line's binary long/flat gate with a continuous scaling factor (min(1.0, vol_target/realized_vol), vol_target=0.15 annualized, vol_window=20) on top of tsmom-spy-qqq's unchanged signal should reduce exposure during volatility spikes with meaningfully less turnover cost than any gated variant, since there is no threshold to chatter across. Killed if Sharpe does not clear 1.0, or if turnover is not meaningfully below tsmom-vol-accel-hysteresis's 0.992369, or if COVID-window scaling provides no material de-risking versus tsmom-spy-qqq's fully-invested baseline.",
  "signal_spec": { "language": "python", "entrypoint": "strategies/tsmom_vol_target.py:Signal" },
  "risk": { "max_position_pct": 5.0, "stop_loss_pct": 2.0, "stop_loss_cooldown_sessions": 10 },
  "lifecycle": "retired",
  "scorecard": {
    "sharpe_wf": 0.741615, "sortino_wf": 1.092855, "max_drawdown_bt": 1.697303,
    "sharpe_paper": null, "max_drawdown_paper": null, "pnl_live": null,
    "rank": null
  }
}
```

## Evidence

Real walk-forward backtest (2016-01-01 to 2024-12-31, `folds=12`, real
SPY+QQQ Alpaca data, `data/results/tsmom-vol-target/`): Sharpe 0.741615,
Sortino 1.092855, max drawdown 1.697303% (best of every strategy in the
momentum line so far), **turnover 0.496432 — essentially matching
[[tsmom-spy-qqq]]'s own ungated 0.465489**, a fraction of both gated
variants' (0.992369 / 1.146023). OOS holdout (trailing 25%, split
2022-09-29): in-sample Sharpe 0.605875, OOS Sharpe 1.076914 — improves on
in-sample again, the fourth consecutive strategy in this line to do so.
Fold Sharpes: `[0.0, 1.451, 1.082, -0.212, 0.771, 0.398, 1.569, 1.62,
-1.41, 1.275, 1.193, 1.162]`.

Falsification check (raw signal, `scripts/tsmom_vol_target_backtest.py`)
— average position weight during known downtrends (this signal doesn't
binarize, so "flat fraction" isn't the metric; average weight is):

| window | symbol | avg weight | fully-flat % |
|---|---|---|---|
| COVID crash | SPY | 0.417 | 0.0% |
| COVID crash | QQQ | 0.368 | 0.0% |
| 2022 bear market | SPY | 0.380 | 48.0% |
| 2022 bear market | QQQ | 0.248 | 52.0% |

**Both halves of the hypothesis came true, and the outcome is still a
retirement — the cleanest and most informative one in this line.**
Turnover concern: fully resolved — continuous scaling costs essentially
nothing extra over the ungated baseline (0.496 vs 0.465), confirming that
constant small rebalancing is far cheaper than any discrete gate
crossing. COVID de-risking: real and material — average exposure during
the crash dropped to ~39% of full size on both symbols, never even
touching 0% (unlike a gate, this never claims to fully evacuate, only to
scale down) yet clearly participating less in the drawdown. Despite both
of those working exactly as designed, aggregate Sharpe (0.742) still
falls short of [[tsmom-spy-qqq]]'s ungated 0.813366, because the vol
target scales down exposure during *any* elevated-vol period, not only
the bad ones — several of tsmom's best folds (e.g. fold 4: 1.237 → 0.771,
fold 6: 1.816 → 1.569, fold 7: 1.771 → 1.62) also carry above-target
realized vol and got scaled down right along with the crash periods.
Realized-vol level alone doesn't distinguish "good vol" (a strong,
volatile trending rally) from "bad vol" (a crash) for this signal.

## Lifecycle history

- 2026-07-21 — created at `research` — structurally different follow-up
  to the vol-gate line (tsmom-vol-accel, tsmom-vol-accel-hysteresis),
  replacing the binary gate with a continuous vol-target scalar;
  vol_window/vol_target fixed before any backtest run at values already
  established elsewhere in this vault, not searched fresh. Includes
  `stop_loss_cooldown_sessions: 10` (Option C) from the start per
  [[stop-loss-rearm-coupling]].
- 2026-07-21 — retired — Sharpe 0.741615 / Sortino 1.092855, short of the
  1.0/1.2 gate and of tsmom-spy-qqq's ungated 0.813366/1.216489. Both
  specific predictions this page made came true: turnover dropped to
  essentially the ungated baseline (0.496432 vs 0.465489 — the vol-gate
  line's turnover problem is fully solved by going continuous), and
  COVID-window exposure genuinely scaled down (average weight ~0.39 on
  both symbols, vs. full exposure in the ungated baseline). Net effect
  still negative because vol-targeting cuts exposure symmetrically in
  high-vol-but-good periods along with high-vol-bad ones — several of
  tsmom's strongest folds carry above-target realized vol and got scaled
  down too. This closes the entire vol-overlay branch of the momentum
  line (three variants: binary gate, hysteresis, continuous scaling) with
  a clean, complete finding: the turnover-vs-protection tradeoff is fully
  solvable (continuous scaling gets it essentially for free), but
  volatility level alone is the wrong signal to condition exposure on for
  this base strategy — it doesn't separate the folds that deserve
  de-risking from the ones that don't. A mechanism that distinguishes
  those (e.g. conditioning on trend strength or drawdown-from-high rather
  than raw realized vol) is the flagged next idea if this specific
  question gets revisited; otherwise this line is closed.
