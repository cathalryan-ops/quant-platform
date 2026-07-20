---
type: concept
created: 2026-07-20
---

# Stop-Loss Re-Arm Coupling

A risk-overlay design trap: when a stop-loss's re-arm condition depends on
the same signal event that a trend-persistent, rare-reversal strategy uses
to flip direction, a stop can lock a position out of the market for far
longer than the stop itself was ever meant to protect against — including
through the exact recovery that would have made the original entry
correct.

## The mechanism

[[market-structure-shift]]-style signals (see [[ms-shift-spy]]) only
reverse on a [[displacement]]-confirmed structure break — a deliberately
rare event, because that rarity is what makes the signal trend-following
rather than noise-following. A signal built this way can hold one
direction for many months at a stretch; that persistence is a feature, not
a bug, of the underlying hypothesis.

The problem appears when a stop-loss's re-arm rule is gated on that same
rare reversal event ("stay flat until the raw signal produces a fresh
0→>0 transition"). An ordinary pullback — nowhere near a real trend
reversal — can breach the stop and force the position flat. If the trend
itself doesn't actually reverse (the common case, precisely because
reversals are rare by construction), the position has no way back in until
the signal eventually does flip, which can be many months away. The stop
correctly avoids a small loss and then, as an unintended side effect, sits
out the entire subsequent recovery.

## Concrete evidence

Found while investigating why enforcing [[ms-shift-spy]]'s manifest-declared
`risk.stop_loss_pct` (previously validated for shape but never enforced —
see [[ms-shift-spy-high-displacement]]'s Lifecycle history) made
walk-forward Sharpe *worse*, not better, on both v1 and v2.

Isolated on ms-shift-spy-v1, QQQ, the fold spanning 2022-10-03 →
2023-07-03: the raw signal goes long on 2022-11-30 (close 293.36) and does
not flip flat again until 2023-09-20 (close 364.54) — a single ~10-month
continuous trend leg, +24%. Under plain stop-loss enforcement: entry fills
2022-12-01 @293.72, stopped out 4 sessions later on 2022-12-05 (ordinary
low-breach, -2%) — and because the raw signal never revisits 0 for the
next ten months, the position cannot re-arm and sits out almost the entire
rally, only re-entering 2023-10-06 @364.70, essentially at the top, just
as the move was ending.

## The fix: Option C, combined re-arm

Implemented in `sandbox/backtest/backtest/risk.py` (`apply_stop_loss`) and
mirrored in `engine-core/src/engine.rs` (`StopLossState`), manifest field
`risk.stop_loss_cooldown_sessions`. Once stopped out, a position re-arms
on whichever of these fires first:

- **(A)** the raw signal produces a fresh 0→>0 transition — the original
  safety property, ungated by cooldown (already rare; nothing to protect
  against here).
- **(B)** `stop_loss_cooldown_sessions` have elapsed since the stop AND
  the current close reclaims (≥) the entry price that triggered the stop
  — bounds how long the slow-to-reverse case can lock a position out of a
  recovery the raw signal itself would have ridden.

## Out-of-sample validation

Ran ms-shift-spy-v1 and -v2 through the real `engine.py`/vectorbt path
(fees, slippage — not a simplified model), using `sandbox/backtest/backtest/oos.py`'s
holdout check with `oos_fraction=0.25` (trailing 3 of 12 walk-forward
folds, chosen to start at 2022-09-29 and so fully cover the lockout fold
above) and the default `reject_threshold=0.35`. `cooldown_sessions=10` was
fixed in advance (same value already committed to in
`sandbox/backtest/scripts/rearm_validation.py`, not tuned against this
result — see the overfitting caution already on record in
[[ms-shift-spy-high-displacement]]'s Lifecycle history).

| variant | v1 OOS check | v2 OOS check |
|---|---|---|
| True original (fresh-signal re-arm only, no price-reclaim) | **REJECTED** (+74.0% degradation) | **REJECTED** (+207.9% degradation) |
| Option C, cooldown=10 | PASSED (−4.4% — OOS *better* than in-sample) | PASSED (−61.8%) |

The true original design — plain enforcement of the manifest's declared
stop, with no price-reclaim path — fails the new OOS gate on both
strategies, driven by exactly this lockout mechanism. Option C passes
cleanly on both.

**This validates the mechanism, not the strategies.** `passed_thresholds`
is still `false` for every variant tested, Option C included — the base
walk-forward Sharpe/Sortino gate (min 1.0 / 1.2 in
`contracts/promotion_thresholds.toml`) isn't met regardless (best case
observed: v2 Sharpe ≈0.76). [[ms-shift-spy]] and
[[ms-shift-spy-high-displacement]] remain correctly `retired`; Option C
fixes a structural risk-overlay bug, it doesn't resurrect either
strategy's promotion case.

Reproducibility note, same caveat as both strategy pages: this run used
the pinned `data/us_equities/daily/QQQ_SPY_2016-01-01_2024-12-31.parquet`
snapshot (`data/` is gitignored) and was recorded manually rather than
through the automated ranker pipeline. Output sits at
`data/results/_option_c_oos_validation/` — deliberately not written to
either strategy's canonical `data/results/<id>/` path, which remains each
strategy's original recorded retirement evidence.

## Generalization

Any risk overlay whose re-arm/reset condition is coupled to the same rare
event the underlying signal uses to change direction is at risk of this
failure mode — not specific to `ms_shift` or to stop-losses specifically.
The general principle: a risk control's own recovery condition should be
evaluated on its own terms (price, time, volatility), not silently
inherited from whatever makes the signal itself rare.
