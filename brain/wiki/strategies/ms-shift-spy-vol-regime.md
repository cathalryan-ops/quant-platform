---
type: strategy
created: 2026-07-20
---

# MS Shift SPY — Volatility Regime Gate

A single-variable follow-up to [[ms-shift-spy]] (v1), orthogonal to
[[ms-shift-spy-high-displacement]] (v2)'s displacement-magnitude axis:
same signal, unchanged, gated to a volatility regime instead of a
displacement threshold.

## Hypothesis

[[ms-shift-spy]]'s edge is conditional on the prevailing volatility
regime, not (only) on displacement magnitude — a question v2 didn't
test (v2 varied displacement_mult, holding everything else, including
implicit regime exposure, fixed). Reuses v1's exact signal (swing_lookback=3,
atr_period=14, displacement_mult=1.5) unmodified and adds one independent
gate: trade only while trailing 20-day annualized realized volatility
falls within [12%, 35%]. Below the band is unusually calm — a "displaced"
bar measured against a nearly-flat ATR is more likely noise than a
genuine structural break. Above the band is crisis-level vol, where gap
risk and discontinuous pricing undermine the forced-exit mechanism the
hypothesis relies on ([[stop-loss-rearm-coupling]] is a related but
distinct failure mode — that one is about re-arm timing, this is about
whether the entry signal itself is trustworthy in extreme regimes).

Vol band and window fixed before any backtest ran: 20 trading days is the
same standard realized-vol window used in [[mean-reversion-spy-qqq]]; 12%
and 35% annualized are round numbers bracketing SPY's typical realized-vol
range in ordinary conditions (SPY's long-run realized vol center is
roughly 15-16% annualized) while excluding both unusually calm markets and
crisis-level spikes (2008, 2020) — not fit to this dataset's fold
boundaries.

**Killed if:** walk-forward Sharpe (same 2016-2024 window, 12 folds, 5 bps
fees + 5 bps slippage) fails to clear the same `backtest_to_paper` gate
already used for this family (Sharpe ≥1.0, Sortino ≥1.2). **Also killed**
if the gate filters out v1's three previously-strong folds (2019-10→2020-07
COVID crash+recovery, 2020-07→2021-04 recovery, 2023-07→2024-04 AI rally)
to near-zero activity — that would mean the regime-conditioning story is
backwards (the edge lives in exactly the high-vol regime this gate
excludes), falsifying the hypothesis regardless of the aggregate number.

## Mechanism

Identical underlying premise to [[ms-shift-spy]] — see
[[market-structure-shift]] and [[displacement]]. The added claim is that
displacement's reliability as a signal of genuine participant-driven
structural change is itself regime-dependent: in near-zero volatility,
the ATR baseline is so small that ordinary noise can register as
"displaced"; in crisis-level volatility, price action becomes
discontinuous (gaps, halts, liquidity vacuums) in ways that break the
forced-exit-fuels-continuation mechanism even if a genuine structural
shift is occurring.

## Falsification test

Compare fold-by-fold Sharpe against v1's already-recorded 12-fold
breakdown (see [[ms-shift-spy]]'s Lifecycle history) directly, not just
the aggregate number: the hypothesis predicts the gate should preserve or
improve v1's three strong folds while filtering out exposure during the
mediocre folds. If the strong folds are gutted instead, or the mediocre
folds are unaffected, the regime story is false regardless of what the
aggregate Sharpe reads.

## Manifest

```strategy_manifest
{
  "schema_version": "1.0.0",
  "id": "ms-shift-spy-vol-regime",
  "wiki_page": "brain/wiki/strategies/ms-shift-spy-vol-regime.md",
  "market": "us_equities",
  "family": "ms_shift",
  "universe": ["SPY", "QQQ"],
  "hypothesis": "ms-shift-spy's edge is conditional on the volatility regime, not only on displacement magnitude: gating v1's unchanged signal to only trade while trailing 20-day annualized realized vol is within [0.12, 0.35] will preserve or improve walk-forward Sharpe versus v1's 0.674/0.657; killed if Sharpe does not clear 1.0, or if the gate filters out v1's three strongest folds.",
  "signal_spec": { "language": "python", "entrypoint": "strategies/ms_shift_vol_regime.py:Signal" },
  "risk": { "max_position_pct": 5.0, "stop_loss_pct": 2.0, "stop_loss_cooldown_sessions": 10 },
  "lifecycle": "retired",
  "scorecard": {
    "sharpe_wf": 0.120134, "sortino_wf": 0.31536, "max_drawdown_bt": 0.7861,
    "sharpe_paper": null, "max_drawdown_paper": null, "pnl_live": null,
    "rank": null
  }
}
```

## Evidence

Real walk-forward backtest (2016-01-01 to 2024-12-31, `folds=12`, real
SPY+QQQ Alpaca data, `data/results/ms-shift-spy-vol-regime/`): Sharpe
0.120134, Sortino 0.31536, max drawdown 0.7861% (turnover 0.457441, about
25% higher than v1's 0.367). OOS holdout (trailing 25%, split 2022-09-29):
in-sample Sharpe 0.509628, OOS Sharpe 0.754881 — technically *passes* the
OOS check (OOS better than in-sample), but that's beside the point given
the aggregate gate result below.

Fold-by-fold comparison against v1's canonical recorded folds
(chronological):

| fold | v1 (orig) | vol-regime | |
|---|---|---|---|
| 0 | -0.087 | -0.11 | |
| 1 | 0.471 | **-1.777** | |
| 2 | 0.818 | **-0.939** | |
| 3 | 0.536 | 0.0 | filtered out entirely |
| 4 | 0.096 | 0.74 | |
| 5 | 2.086 | 1.341 | strong fold, preserved |
| 6 | 1.292 | 1.457 | strong fold, preserved |
| 7 | 0.378 | -0.629 | |
| 8 | 0.0 | 0.0 | |
| 9 | 0.613 | 1.062 | |
| 10 | 1.7 | 1.279 | strong fold, preserved |
| 11 | -0.022 | -0.983 | |

## Lifecycle history

- 2026-07-20 — created at `research` — proposed as an orthogonal
  follow-up to v1, isolating the volatility-regime question from v2's
  displacement-magnitude question; vol_window/vol_low/vol_high fixed
  before any backtest run, not searched. Risk config includes
  `stop_loss_cooldown_sessions: 10` (Option C) from the start, since that
  mechanism is now validated — see [[stop-loss-rearm-coupling]] — no
  reason to test new candidates against the known-broken re-arm design.
- 2026-07-20 — retired — Sharpe 0.120134 / Sortino 0.31536, nowhere near
  the 1.0/1.2 gate. The narrower falsification test gives a genuinely
  interesting negative result rather than a flat miss: the three
  previously-strong folds (5, 6, 10) *were* preserved roughly intact, so
  the gate didn't gut the good part of the signal as originally feared —
  but folds 1 and 2, previously solidly positive (0.471, 0.818), flipped
  sharply negative (-1.777, -0.939) under the gate, and folds 3/8 lost all
  trading activity entirely. Net effect: aggregate Sharpe (0.120) is
  *worse* than v1's ungated baseline (0.674), not better. The
  regime-conditioning hypothesis as specified is falsified — filtering by
  a fixed absolute volatility band doesn't cleanly separate "noise" from
  "signal" periods; it removes activity in ways that sometimes cut off
  subsequently-good moves rather than only removing genuinely bad ones.
  Not a parameter-tuning target (the band edges are not the finding here);
  a genuinely different mechanism is the right next step.
