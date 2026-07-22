---
type: strategy
created: 2026-07-22
---

# TSMOM / MS-Shift / Dual-Momentum Blend

Direct follow-up to [[tsmom-ms-shift-blend]] (Sharpe 0.884266, Sortino
1.296607 — this vault's best result, and the only lever that has ever
beaten a single-leg baseline: every gate tried on either leg individually
made it worse, but combining two structurally independent edges beat both).
The natural next question is whether a third independent leg pushes it
further, or whether two was already capturing most of the available
diversification.

## Candidate screening (why dual-momentum, not a re-used gate)

Every other already-tested SPY/QQQ-universe strategy was ruled out before
writing any code, to avoid picking a third leg that looks cheap but isn't:

- [[tsmom-vol-accel]], [[tsmom-vol-accel-hysteresis]], `tsmom-vol-target`,
  [[tsmom-breadth-gate]] — all are gates *on top of* tsmom-spy-qqq's own
  signal. Correlated with the tsmom leg by construction; adding one back in
  isn't a third independent bet, it's tsmom with less exposure.
- [[ms-shift-spy-vol-regime]] — same problem, gates ms-shift's own signal.
- [[mean-reversion-spy-qqq]] — its own pre-registered falsification test
  found triggered-entry forward returns statistically indistinguishable
  from random (SPY z≈-0.03, QQQ z≈-0.95). A confirmed mechanism-level null,
  not a weak-but-real edge — blending it in adds variance with no offsetting
  expected return, which dilutes Sharpe rather than raising it.
- `turn-of-month-spy-qqq` (Sharpe 0.022) — same problem, a clean null (its
  own falsification test failed outright too).
- [[52wk-high-spy-qqq]] (Sharpe 0.625) — real edge, but ~80% raw signal
  agreement with tsmom-spy-qqq, already documented as "related, not
  independent." Wrong axis for a diversifying third leg.

[[dual-momentum-equity-bond-gold]] (Sharpe 0.101427, retired) is the one
candidate that clears both bars: its own falsification test confirmed a
*real*, working mechanism (108 monthly rebalances: SPY 49.1%, GLD 24.1%,
CASH 21.3%, TLT 5.6% — the cash floor genuinely binds and the basket
genuinely rotates across asset classes, not a degenerate always-SPY or
always-flat result), and it reaches TLT/GLD, a risk source neither
tsmom-spy-qqq nor ms-shift-spy-high-displacement can touch (both are
SPY/QQQ only — pure equity beta). Low standalone Sharpe is not
disqualifying here the way it was for mean-reversion/turn-of-month,
because dual-momentum's weakness was diagnosed as *opportunity cost*
(rotating into GLD/TLT during months when SPY's own momentum was
mediocre-but-still-better), not *no real signal at all*.

## Hypothesis

Extend [[signal-blending]] from two legs to three: average tsmom-spy-qqq's,
ms-shift-spy-high-displacement's, and dual-momentum-equity-bond-gold's
position weights at equal 1/3 each (fixed a priori — an equal split,
extending the 2-leg blend's own 50/50 discipline symmetrically rather than
searching for a better split), all three signals fully unchanged (no
re-tuning of any component's own parameters). If dual-momentum's return
stream is meaningfully uncorrelated with the existing two legs — plausible
given its distinct TLT/GLD exposure, but not guaranteed, since its
construction reuses tsmom's identical lookback=252/skip=21 logic on SPY as
one of its three ranked candidates — the 3-way blend's variance should fall
further than its expected return does, raising Sharpe versus the 2-leg
blend.

**Killed if:** walk-forward Sharpe does not clear the 2-leg blend's own
current-engine Sharpe (re-measured fresh in this same run, not the recorded
scorecard number) or the standing 1.0/1.2 gate. **Also checked:** pairwise
correlation of all three legs' daily return streams — specifically whether
dual-momentum's correlation to tsmom-spy-qqq is meaningfully higher than
its correlation to ms-shift (which would indicate the shared SPY-momentum
logic dominates rather than the TLT/GLD diversification).

## Mechanism

See [[signal-blending]] and [[dual-momentum]]. No new causal claim about
any individual mechanism — this is a third data point on the same
portfolio-construction claim the 2-leg blend tested: edges that fire on
different days for different reasons, and here additionally on different
*asset classes*, should partially offset each other's idiosyncratic
drawdowns when held together.

## Falsification test

Compute the Pearson correlation of all three legs' daily portfolio return
streams (each re-run standalone under identical current-engine risk
settings) over the full 2016-2024 sample, alongside the 3-way blend's
Sharpe/Sortino/drawdown/turnover compared directly against the 2-leg
blend and all three individual legs, all measured fresh in the same run.

## Manifest

```strategy_manifest
{
  "schema_version": "1.0.0",
  "id": "tsmom-ms-shift-dualmom-blend",
  "wiki_page": "brain/wiki/strategies/tsmom-ms-shift-dualmom-blend.md",
  "market": "us_equities",
  "family": "swing",
  "universe": ["SPY", "QQQ", "TLT", "GLD"],
  "hypothesis": "Extending tsmom-ms-shift-blend (Sharpe 0.884266) with a third leg, dual-momentum-equity-bond-gold, at equal 1/3 weight per leg (fixed a priori). Killed if walk-forward Sharpe does not clear the 2-leg blend's own current-engine Sharpe or the standing 1.0/1.2 gate.",
  "signal_spec": { "language": "python", "entrypoint": "strategies/tsmom_ms_shift_dualmom_blend.py:Signal" },
  "risk": { "max_position_pct": 5.0, "stop_loss_pct": 2.0, "stop_loss_cooldown_sessions": 10 },
  "lifecycle": "retired",
  "scorecard": {
    "sharpe_wf": 0.863027, "sortino_wf": 1.304873, "max_drawdown_bt": 1.138843,
    "sharpe_paper": null, "max_drawdown_paper": null, "pnl_live": null,
    "rank": null
  }
}
```

## Evidence

Real walk-forward backtest (2016-01-01 to 2024-12-31, `folds=12`, real
16-symbol Alpaca data restricted to SPY/QQQ/TLT/GLD,
`data/results/tsmom-ms-shift-dualmom-blend/`), run alongside fresh
current-engine standalone re-runs of all three legs
(`scripts/tsmom_ms_shift_dualmom_blend_backtest.py`):

| | Sharpe | Sortino | Max DD % | Turnover |
|---|---|---|---|---|
| tsmom-spy-qqq (fresh re-run) | 0.813366 | 1.216489 | 2.305277 | 0.465489 |
| ms-shift-spy-v2 (fresh re-run) | 0.759373 | 1.124019 | 1.044311 | 0.275822 |
| dual-momentum-equity-bond-gold (fresh re-run) | 0.101427 | 0.239986 | 1.401386 | 0.363200 |
| tsmom-ms-shift-blend (2-leg, recorded) | 0.884266 | 1.296607 | 1.234476 | 0.334849 |
| **tsmom-ms-shift-dualmom-blend (3-leg)** | **0.863027** | **1.304873** | **1.138843** | **0.321706** |

**The 3-way blend does not clear its own pre-registered kill criterion:**
Sharpe 0.863027 is *below* the 2-leg blend's 0.884266 (re-measured under
identical current-engine settings), so this is killed as designed, not a
judgment call. Sortino (1.304873), max drawdown (1.138843%), and turnover
(0.321706) all improve slightly on the 2-leg blend — the third leg is not
useless — but the explicit, pre-registered bar was Sharpe versus the 2-leg
baseline, and it misses. Also, as with every strategy in this vault, it
misses the standing 1.0/1.2 gate outright.

Falsification check (pairwise Pearson correlation, all three legs'
standalone daily returns, full sample): tsmom vs ms-shift **0.5522**
(reproduces the 2-leg blend's own recorded number exactly), tsmom vs
dual-momentum **0.5852**, ms-shift vs dual-momentum **0.2584**. This
confirms the risk flagged in the Hypothesis: dual-momentum is *more*
correlated with tsmom-spy-qqq than tsmom and ms-shift are with each other,
not less — consistent with dual-momentum's own construction running
tsmom's identical lookback=252/skip=21 logic on SPY as one of its three
ranked candidates. The genuinely low-correlation pair here is ms-shift vs
dual-momentum (0.2584); tsmom vs dual-momentum is the weak link. Net: this
3rd leg adds real but only partial diversification (through TLT/GLD and
through its low correlation to the ms-shift leg specifically), which is
enough to nudge Sortino/drawdown/turnover in the right direction but not
enough to overcome its shared-SPY-logic correlation to the tsmom leg and
lift the blend's Sharpe above two legs alone.

Fold Sharpes (3-leg blend): `[-0.066, 1.306, 1.296, -0.458, 1.738, -0.141,
1.327, 1.789, -1.19, 1.926, 1.524, 1.305]`. OOS holdout (trailing 25%,
split 2022-09-29): in-sample Sharpe 0.572984, OOS Sharpe 1.380514 —
improves on in-sample (PASSED), the same pattern nearly every strategy in
this vault shows on this split.

## Lifecycle history

- 2026-07-22 — created at `research` — direct follow-up to
  [[tsmom-ms-shift-blend]]; candidate screening ruled out every other
  already-tested strategy before implementation (see above). Blend weights
  fixed at an equal 1/3 split before any backtest run; all three component
  signals' own parameters carried over unchanged. Includes
  `stop_loss_cooldown_sessions: 10` (Option C) from the start.
- 2026-07-22 — retired — Sharpe 0.863027, below the 2-leg blend's
  0.884266 (re-measured fresh in the same run) — fails its own
  pre-registered kill criterion, so this is a clean, designed-for outcome,
  not a marginal call. Sortino (1.304873), max drawdown (1.138843%), and
  turnover (0.321706) all improve slightly on the 2-leg blend, so the
  3rd leg is not dead weight, but the bar that mattered was Sharpe vs. the
  2-leg baseline. The falsification check explains why: dual-momentum's
  correlation to tsmom-spy-qqq (0.5852) is *higher* than tsmom and
  ms-shift's correlation to each other (0.5522), driven by dual-momentum
  reusing tsmom's own lookback/skip logic on SPY as one of its three
  candidates — this 3rd leg was never as independent of the tsmom leg as
  the screening hoped, even though it's genuinely less correlated with the
  ms-shift leg (0.2584). Not a parameter-tuning target: `weight_tsmom =
  weight_ms_shift = weight_dual_mom = 1/3` was fixed a priori and searching
  for a better split on this same fixed window repeats the overfitting
  pattern already flagged twice in this vault. Flagged next step if this
  axis is revisited: a genuinely SPY-independent third leg (e.g. one that
  never touches SPY at all, unlike dual-momentum's three-candidate basket)
  would be a cleaner test of whether a third leg can help, since this run
  couldn't cleanly separate "third leg doesn't help" from "this particular
  third leg secretly shares tsmom's SPY logic."
