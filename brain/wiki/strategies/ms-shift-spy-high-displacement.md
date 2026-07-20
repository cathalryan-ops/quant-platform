---
type: strategy
created: 2026-07-20
---

# MS Shift SPY — High Displacement (v2)

Single-variable follow-up to [[ms-shift-spy]] (v1, retired 2026-07-20). Not
a new mechanism — a stricter version of the same one, isolating a single
question the v1 postmortem raised.

## Hypothesis

v1's real 12-fold walk-forward result (see [[ms-shift-spy]]'s Lifecycle
history and `brain/raw/ms-shift-spy-v1-fold-regime-hypothesis.md`) showed
its edge concentrated in 3 of 12 folds — all clean, sustained continuation
windows (COVID crash+recovery, the following 2020-21 recovery, the 2023-24
AI rally) — while the other 9 folds sat in a mediocre 0.0-0.82 Sharpe
band. v1's displacement filter (range ≥ 1.5× 14-day ATR) may be too loose,
letting through low-conviction structure breaks that dilute the average
with noise trades rather than concentrating on the high-conviction breaks
that actually predict continuation.

**Hypothesis:** raising the displacement threshold to 2.0× ATR (v1's 1.5×
→ 2.0×, everything else unchanged) will act as a crude conviction filter,
pruning weak entries and raising walk-forward Sharpe versus v1's 0.674
(12-fold) / 0.657 (5-fold) — even at the cost of materially fewer trades.

**Killed if:** walk-forward Sharpe with mult=2.0 is not clearly better
than v1 (say, doesn't clear ≥0.85) — a wash or a decline would mean
displacement magnitude isn't distinguishing good entries from noise, and
the mediocre folds are mediocre for some other reason. **Also killed if**
trade count collapses to a handful of trades over the 9-year period —
that would make any Sharpe reading statistically meaningless rather than
a real result, and needs to be checked before the Sharpe number is
trusted at all (see Falsification test).

## Mechanism

Identical to v1 — see [[market-structure-shift]] and [[displacement]].
The only added claim here is that displacement *magnitude* is a
reasonable proxy for entry conviction, so filtering harder on it should
improve selectivity without abandoning the underlying premise.

## Calibration (why 2.0, not 3.0)

Before picking a value, candidate multipliers (1.5, 1.75, 2.0, 2.25, 2.5,
3.0) were sanity-checked against synthetic i.i.d.-noise OHLC series
(offline, no live data needed — this only tests firing frequency, not
performance). Result: 3.0 fired **zero times** over a synthetic
9-year-equivalent series across 5 seeds; even 2.0 was sparse (~0.4
position changes per run). Real markets cluster volatility far more than
independent Gaussian draws (autocorrelated true range, fat tails), so
this systematically *underestimates* real firing frequency — it's a lower
bound, not a prediction — but it was enough to rule out 3.0 as almost
certainly too aggressive for a statistically meaningful test, and to
choose 2.0 as a genuine-but-not-reckless step up from v1's 1.5.

## Falsification test

Run the existing harness against the same manifest shape as v1
(SPY+QQQ, 2016-01-01 to 2024-12-31, `folds=12` to match the resolution
that produced v1's fold breakdown). Before trusting the Sharpe number,
check the trade count / turnover first — if it's too sparse to be
meaningful (single digits of trades over 9 years), that alone falsifies
the "2.0 is a usable threshold" premise regardless of what the Sharpe
says. If trade count is reasonable, compare the fold-by-fold Sharpes
directly against v1's 12-fold breakdown: the hypothesis predicts the
weak/mediocre folds should either drop out (fewer or no trades in those
windows) or improve, while the 3 strong folds (2019-10→2020-07,
2020-07→2021-04, 2023-07→2024-04) should be preserved.

## Manifest

```strategy_manifest
{
  "schema_version": "1.0.0",
  "id": "ms-shift-spy-v2",
  "wiki_page": "brain/wiki/strategies/ms-shift-spy-high-displacement.md",
  "market": "us_equities",
  "family": "ms_shift",
  "universe": ["SPY", "QQQ"],
  "hypothesis": "Raising the displacement threshold from 1.5x to 2.0x 14-day ATR (v1's only other parameters unchanged) filters out low-conviction structure breaks and raises walk-forward Sharpe versus v1's 0.674 (12-fold); killed if Sharpe does not clear 0.85 or if trade count collapses to a statistically meaningless handful of trades over 2016-2024.",
  "signal_spec": { "language": "python", "entrypoint": "strategies/ms_shift_spy_high_displacement.py:Signal" },
  "risk": { "max_position_pct": 5.0, "stop_loss_pct": 2.0 },
  "lifecycle": "retired",
  "scorecard": {
    "sharpe_wf": 0.813341, "sortino_wf": 1.199802, "max_drawdown_bt": 1.179691,
    "sharpe_paper": null, "max_drawdown_paper": null, "pnl_live": null,
    "rank": null
  }
}
```

## Evidence

Real walk-forward backtest (2016-01-01 to 2024-12-31, `folds=12`, real
SPY+QQQ Alpaca data, run by the operator): Sharpe 0.813341, Sortino
1.199802, max drawdown 1.179691%, turnover 0.185723 (about half of v1's
0.367). Same reproducibility caveat as v1: `data/` is gitignored, this
result is manually recorded, not reproducible from this repo alone.

Per-fold Sharpes (chronological, same 12-fold boundaries as v1's
follow-up — see [[ms-shift-spy]]): [-0.066, 1.171, 1.425, 0.0, 0.0,
1.797, 0.982, 0.0, 0.0, 1.444, 1.721, 1.287]. Four folds (indices 3, 4,
7, 8 — the same windows that were v1's mediocre-but-positive folds:
0.536, 0.096, 0.378, 0.0) went to exactly 0.0, meaning the stricter
filter stopped trading in them entirely rather than trading them
better. Where it did still trade, results are mixed relative to v1:
folds 1, 2, 9, 11 improved meaningfully (fold 11 flipped from -0.022 to
1.287), but folds 5 and 6 — two of v1's three standout folds (COVID
crash+recovery and the following 2020-21 recovery) — got slightly
*worse* (2.086→1.797, 1.292→0.982). The filter's value is concentrated
in avoiding/neutralizing mediocre periods, not in improving the best
ones.

## Lifecycle history

- 2026-07-20 — created at `research` — proposed as a single-variable
  follow-up to [[ms-shift-spy]]'s (v1) retirement postmortem; parameter
  choice calibrated against synthetic firing-frequency checks (see
  Calibration section above) rather than picked arbitrarily.
- 2026-07-20 — retired — Real backtest confirms the hypothesis
  *directionally* (Sharpe 0.657→0.813, turnover halved) but still fails
  `contracts/promotion_thresholds.toml`'s `[backtest_to_paper]` gate:
  Sharpe 0.813341 vs min 1.0 (missed by 0.186659 — the binding
  constraint), Sortino 1.199802 vs min 1.2 (missed by 0.000198 —
  essentially a tie, but Sharpe alone still fails the gate). Max
  drawdown 1.179691% is well within the 15% cap. Retired per the same
  manual-record rationale as v1 (`data/` gitignored, not reproducible
  from this repo). **Explicit caution against continuing to hand-tune
  `displacement_mult` on this same fixed 2016-2024 window:** this is
  now the second iteration on one parameter against one fixed historical
  sample, and "getting closer each try" is exactly the pattern that
  produces overfit, non-generalizing results if pursued further by
  parameter search alone — the Sortino near-miss should not be read as
  "one more nudge will clear it." A structurally different lever is a
  better next step than a third tuning pass on the same knob: see
  [[ms-shift-spy]]'s engine gap — `risk.stop_loss_pct` (declared 2.0% in
  both v1 and v2's manifests) is validated for shape but never actually
  enforced in the backtest simulation (`vbt.Portfolio.from_orders()` is
  called with no `sl_stop`/`sl_trail` parameter). Positions currently
  ride purely on the signal flipping back to flat, with no independent
  stop-loss exit — meaning failed-breakout trades (plausibly the source
  of the mediocre-fold drag identified in v1's postmortem) can run
  further than the manifest's own declared risk tolerance before
  exiting. Implementing a real stop-loss is a genuinely different
  mechanism from entry filtering, targets the specific failure mode
  already identified, and is testable on the same historical data
  without repeating the overfitting risk of re-tuning the same
  displacement knob a third time.
- 2026-07-20 — engine gap closed, then structurally re-investigated —
  `risk.stop_loss_pct` is now enforced. Plain enforcement made things
  worse (same root cause as [[ms-shift-spy]]'s v1: a re-arm/trend-persistence
  coupling bug — full mechanism at [[stop-loss-rearm-coupling]]), fixed
  via a combined re-arm rule ("Option C", `stop_loss_cooldown_sessions`,
  fixed at 10 sessions in advance — not re-tuned against this result,
  consistent with the no-further-parameter-tuning caution above). Real
  out-of-sample validation (`oos.py`, trailing 25% holdout covering the
  same 2022-10→2023-07 window): the true original re-arm design is
  OOS-rejected (+207.9% degradation vs the 35% threshold); Option C
  passes cleanly (-61.8%, OOS *better* than in-sample). This validates
  the re-arm fix structurally, not this strategy's promotion case —
  `passed_thresholds` is still `false` with Option C (Sharpe ~0.76,
  still below the 1.0 minimum, the same binding constraint as before).
  This page stays `retired`.
