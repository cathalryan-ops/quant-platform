---
type: strategy
created: 2026-07-22
---

# TSMOM / MS-Shift / TLT-GLD Blend

Follow-up to [[tsmom-ms-shift-dualmom-blend]]'s retirement (Sharpe
0.863027, below the 2-leg blend's 0.884266 — killed by its own criterion
because dual-momentum-equity-bond-gold turned out *more* correlated with
tsmom-spy-qqq, 0.5852, than tsmom and ms-shift are with each other,
0.5522, due to shared SPY-momentum logic in dual-momentum's construction).

[[tsmom-tlt-gld]] was built and tested specifically to break that
confound: same absolute-momentum mechanism, applied to TLT/GLD, sharing
zero symbols with either existing leg. It measured near-zero correlation
to both (0.0051 vs tsmom-spy-qqq, 0.0689 vs ms-shift-spy-high-
displacement) despite a weak-but-genuinely-real standalone Sharpe
(0.173042 — not a mechanism-level null like mean-reversion or
turn-of-month; OOS improves on in-sample). This strategy tests that leg
in the blend.

## Hypothesis

Extend [[signal-blending]] with tsmom-tlt-gld as the third leg instead of
dual-momentum-equity-bond-gold, equal 1/3 weight per leg (fixed a priori,
same discipline as every blend attempt in this vault), all three
component signals fully unchanged. Diversification theory predicts that
near-zero correlation lets even a weak edge add expected return to a
portfolio without proportionally adding variance — the opposite profile
from dual-momentum's stronger-but-more-correlated leg, which pulled Sharpe
down net of its correlation cost. If that holds here, the 3-way blend
should beat the 2-leg blend's 0.884266 where the dual-momentum attempt
(0.863027) did not, precisely because near-zero correlation is a
structurally different regime from moderate correlation, not just a
smaller version of the same effect.

**Killed if:** walk-forward Sharpe does not clear the 2-leg blend's own
current-engine Sharpe (0.884266, re-measured fresh in this same run) or
the standing 1.0/1.2 gate — identical criterion to
tsmom-ms-shift-dualmom-blend, for a direct apples-to-apples comparison of
the two third-leg candidates.

## Mechanism

See [[signal-blending]] and [[time-series-momentum]]. No new causal claim
— tsmom-tlt-gld's own mechanism (trend persistence in rate-cycle and
safe-haven/inflation-cycle regimes) is unchanged. The only claim under
test here is portfolio construction: does near-zero correlation between a
weak edge and two moderate-Sharpe edges lift the combination's Sharpe more
than a stronger-but-more-correlated third leg did.

## Falsification test

Same structure as tsmom-ms-shift-dualmom-blend's: report the 3-way
blend's Sharpe/Sortino/drawdown/turnover against the 2-leg blend and all
three individual legs, all measured fresh in the same run, plus the
pairwise correlations already established on tsmom-tlt-gld's own page —
read together as a direct test of whether near-zero correlation actually
beats moderate correlation for blend-lift purposes on this data, not just
a hypothetical.

## Manifest

```strategy_manifest
{
  "schema_version": "1.0.0",
  "id": "tsmom-ms-shift-tltgld-blend",
  "wiki_page": "brain/wiki/strategies/tsmom-ms-shift-tltgld-blend.md",
  "market": "us_equities",
  "family": "swing",
  "universe": ["SPY", "QQQ", "TLT", "GLD"],
  "hypothesis": "Extending tsmom-ms-shift-blend (Sharpe 0.884266) with tsmom-tlt-gld as a third leg at equal 1/3 weight (fixed a priori), on the strength of its near-zero correlation to both existing legs (0.0051 / 0.0689) despite a weak standalone Sharpe (0.173042). Killed if walk-forward Sharpe does not clear the 2-leg blend's own current-engine Sharpe or the standing 1.0/1.2 gate.",
  "signal_spec": { "language": "python", "entrypoint": "strategies/tsmom_ms_shift_tltgld_blend.py:Signal" },
  "risk": { "max_position_pct": 5.0, "stop_loss_pct": 2.0, "stop_loss_cooldown_sessions": 10 },
  "lifecycle": "retired",
  "scorecard": {
    "sharpe_wf": 0.989632, "sortino_wf": 1.506836, "max_drawdown_bt": 1.089789,
    "sharpe_paper": null, "max_drawdown_paper": null, "pnl_live": null,
    "rank": null
  }
}
```

## Evidence

Real walk-forward backtest (2016-01-01 to 2024-12-31, `folds=12`, real
16-symbol Alpaca data restricted to SPY/QQQ/TLT/GLD,
`data/results/tsmom-ms-shift-tltgld-blend/`), run alongside fresh
current-engine standalone re-runs of all three legs
(`scripts/tsmom_ms_shift_tltgld_blend_backtest.py`):

| | Sharpe | Sortino | Max DD % | Turnover |
|---|---|---|---|---|
| tsmom-spy-qqq (fresh re-run) | 0.813366 | 1.216489 | 2.305277 | 0.465489 |
| ms-shift-spy-v2 (fresh re-run) | 0.759373 | 1.124019 | 1.044311 | 0.275822 |
| tsmom-tlt-gld (fresh re-run) | 0.173042 | 0.402854 | 2.314457 | 0.594002 |
| tsmom-ms-shift-blend (2-leg, recorded) | 0.884266 | 1.296607 | 1.234476 | 0.334849 |
| tsmom-ms-shift-dualmom-blend (3-leg, dual-mom) | 0.863027 | 1.304873 | 1.138843 | 0.321706 |
| **tsmom-ms-shift-tltgld-blend (3-leg, tlt-gld)** | **0.989632** | **1.506836** | **1.089789** | **0.423796** |

**This is the best result in this vault to date, by a wide margin over
the previous best (0.884266).** The kill criterion is cleared decisively
— 0.989632 vs. the 2-leg blend's 0.884266 is a +0.105 improvement, in
sharp contrast to the dual-momentum attempt's -0.021 regression. Sortino
(1.506836) clears the 1.2 gate by the largest margin recorded here. Max
drawdown (1.089789%) is the second-lowest of any blend attempt. **Sharpe
0.989632 misses the standing 1.0 gate by 0.010368 — a 1.0% miss, the
closest any strategy in this vault has ever come**, versus the previous
closest miss (tsmom-ms-shift-blend, 0.884266, a 11.6% miss). Per the
standing 1.0/1.2 gate (unchanged, per the human's 2026-07-22 decision on
tsmom-ms-shift-blend not to loosen it for near-misses), `passed_thresholds`
is `false` and this stays `retired`.

**Falsification check confirms the mechanism directly**: pairwise
correlation tsmom vs ms-shift 0.5522 (reproduces the known number), tsmom
vs tsmom-tlt-gld 0.0051, ms-shift vs tsmom-tlt-gld 0.0689 — both
near-zero. This is the clean comparison the dual-momentum attempt
couldn't provide: a third leg with genuinely near-zero correlation to
both existing legs lifts the blend's Sharpe substantially (+0.105 vs the
2-leg baseline) even though its own standalone Sharpe (0.173) is far
weaker than dual-momentum's-would-be comparison point and barely above a
quarter of either existing leg's. Correlation regime, not standalone
strength, was the deciding factor between the two third-leg candidates —
directly validating the diversification-theory prediction that motivated
building tsmom-tlt-gld in the first place.

Fold Sharpes (3-leg tlt-gld blend): `[-0.066, 1.35, 1.531, -0.91, 2.527,
1.499, 0.986, 1.658, -1.451, 1.379, 1.916, 1.458]` — ten of twelve folds
positive, the highest single-fold Sharpe recorded in this vault (2.527).
OOS holdout (trailing 25%, split 2022-09-29): in-sample Sharpe 0.729028,
OOS Sharpe 1.508223 — improves substantially on in-sample (PASSED), the
same pattern nearly every strategy here shows on this split, though the
in-sample number itself (0.729028) is also the highest in-sample Sharpe
recorded for any blend variant, suggesting this isn't purely an artifact
of a favorable OOS window.

## Lifecycle history

- 2026-07-22 — created at `research` — direct follow-up to
  [[tsmom-ms-shift-dualmom-blend]]'s retirement and [[tsmom-tlt-gld]]'s
  correlation finding; blend weights fixed at equal 1/3 before any
  backtest run, all three component signals' own parameters unchanged.
  Includes `stop_loss_cooldown_sessions: 10` (Option C) from the start.
- 2026-07-22 — retired — Sharpe 0.989632, Sortino 1.506836 — the best
  result recorded in this vault, clearing its own kill criterion (beats
  the 2-leg blend's 0.884266 by +0.105) decisively, unlike the
  dual-momentum third-leg attempt (0.863027, a regression). Misses the
  standing 1.0 Sharpe gate by only 0.010368 (1.0%) — the closest any
  strategy here has ever come, versus the previous closest miss's 11.6%
  gap. `passed_thresholds` stays `false` per the unchanged gate (human
  already declined to loosen it for a near-miss once, on
  [[tsmom-ms-shift-blend]], specifically to preserve the discipline that
  retired every other strategy cleanly — the same reasoning applies here,
  arguably more so since standing pat kept the bar meaningful for
  exactly this kind of even-closer result). Falsification check confirms
  the mechanism: near-zero correlation (0.0051/0.0689) between the third
  leg and both existing legs, contrasted directly against
  dual-momentum's higher correlation (0.5852 to tsmom) and worse blend
  outcome — the clean A/B this vault needed to confirm that correlation
  regime, not standalone Sharpe strength, is what determines whether a
  third leg helps. Not a parameter-tuning target: 1/3 weights fixed a
  priori, stay that way; searching for a better split now, this close to
  the gate, would be exactly the overfitting risk flagged repeatedly in
  this vault. Flagged for human awareness (not a request to loosen the
  gate): this is materially stronger evidence than tsmom-ms-shift-blend's
  own near-miss that a real, non-overfit, triple-diversified combination
  of edges can approach the 1.0 Sharpe bar on this data — worth noting
  even though the standing decision on the gate itself remains unchanged.
- 2026-07-22 — closed — decision (human + agent) not to pursue a fourth
  blend leg: no remaining low-correlation candidate in the pinned
  universe (TLT/GLD spent on this leg; sector ETFs/IWM/DIA share the
  same equity PC1 factor per [[pinned-universe-diversity-2026-07-22]];
  crypto's 2021-only data can't join this 2016-2024 window without
  invalidating every comparison made across the blend-leg-search line).
  Also a process-discipline concern: two candidates already tried
  against the same fixed sample and OOS split, keeping the winner — a
  fourth attempt risks crossing into search-until-it-clears-the-gate.
  See [[blend-leg-search-2026-07-22]] for the full synthesis.