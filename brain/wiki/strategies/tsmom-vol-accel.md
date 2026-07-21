---
type: strategy
created: 2026-07-21
---

# Time-Series Momentum — Volatility-Acceleration Gate

A single-variable follow-up to [[tsmom-spy-qqq]], same discipline as
[[ms-shift-spy-high-displacement]] (v2) and [[ms-shift-spy-vol-regime]]
(v3) before it: reuse the base signal unchanged, add exactly one
independent gate, and isolate whether that one variable fixes the
specific, named limitation the base strategy's retirement identified.

## Hypothesis

[[tsmom-spy-qqq]] was retired as a clean near-miss (Sharpe 0.813 vs. the
1.0 gate) whose own pre-registered falsification test still fired: it was
fully invested through the entire 2020 COVID crash, because a 12-month
trailing-return signal cannot react to a shock that occurs inside its own
lookback window. [[volatility-acceleration]] is a structurally different,
much-shorter-horizon signal aimed squarely at that blind spot: gate the
unchanged tsmom signal off whenever 5-day realized vol expands past
`vol_accel_threshold=1.75`x the 63-day realized-vol baseline, regardless
of what the trend signal itself says.

Parameters fixed before any backtest ran: `vol_short_window=5` (one
trading week — fast enough to react within the same week a shock starts,
which is the entire point), `vol_long_window=63` (one trading quarter —
long enough to be a stable "normal regime" baseline, and deliberately
different from tsmom's own 252-day lookback so this is an independently
causal signal, not a rescaled copy of it). `vol_accel_threshold=1.75`: a
round number reflecting that short-window realized-vol estimates are
naturally noisier than a smoothed quarterly baseline (ratios of
1.2-1.4x occur from ordinary sampling noise even in calm markets), so the
gate needed real headroom above 1.0x to avoid closing on ordinary weeks —
not fit to this dataset's outcome.

**Killed if:** walk-forward Sharpe (2016-2024, 12 folds, 5 bps fees + 5
bps slippage) fails to clear the standing gate (Sharpe ≥1.0, Sortino
≥1.2). **The specific thing this page exists to test:** does the gate
close during the 2020 COVID crash noticeably earlier than tsmom's own
12-month signal ever could? If the gate still leaves the strategy
invested through the bulk of the crash, the hypothesis is falsified on
its own terms regardless of what happens to the aggregate Sharpe.

## Mechanism

See [[volatility-acceleration]] and [[time-series-momentum]]. The
proposed causal story specifically for *why this should help*: realized
volatility itself tends to expand before a slow trend-following signal
can flip sign — the option/vol market and short-horizon price dispersion
react to a regime change days to weeks before a 12-month trailing return
does, because the trailing return is a smoothed average across an entire
year while the vol ratio is a fast, narrow-window comparison. This isn't
a claim that the vol gate predicts direction — only that it can flatten
exposure faster than the trend signal once a shock is actually underway.

## Falsification test

Same falsification harness as [[tsmom-spy-qqq]]'s page (raw signal, flat
fraction during the 2020-02-19 to 2020-04-07 COVID crash window and the
2022-01-03 to 2022-10-12 bear market window), plus a direct comparison:
does flat-time during the COVID window increase materially versus
tsmom-spy-qqq's recorded 0.0%? If not — if the vol-accel gate is just as
blind to this specific shock as the trend signal alone — the mechanism
doesn't do what it claims, independent of the aggregate Sharpe number.

## Manifest

```strategy_manifest
{
  "schema_version": "1.0.0",
  "id": "tsmom-vol-accel",
  "wiki_page": "brain/wiki/strategies/tsmom-vol-accel.md",
  "market": "us_equities",
  "family": "swing",
  "universe": ["SPY", "QQQ"],
  "hypothesis": "tsmom-spy-qqq's unchanged signal, gated off whenever 5-day realized vol expands past 1.75x the 63-day realized-vol baseline, should reduce or eliminate the COVID-crash blind spot (0% flat time in tsmom-spy-qqq) while preserving walk-forward Sharpe; killed if Sharpe does not clear 1.0, or if COVID-window flat time does not increase materially over tsmom-spy-qqq's 0.0%.",
  "signal_spec": { "language": "python", "entrypoint": "strategies/tsmom_vol_accel.py:Signal" },
  "risk": { "max_position_pct": 5.0, "stop_loss_pct": 2.0, "stop_loss_cooldown_sessions": 10 },
  "lifecycle": "retired",
  "scorecard": {
    "sharpe_wf": 0.533888, "sortino_wf": 0.872186, "max_drawdown_bt": 1.878151,
    "sharpe_paper": null, "max_drawdown_paper": null, "pnl_live": null,
    "rank": null
  }
}
```

## Evidence

Real walk-forward backtest (2016-01-01 to 2024-12-31, `folds=12`, real
SPY+QQQ Alpaca data, `data/results/tsmom-vol-accel/`): Sharpe 0.533888,
Sortino 0.872186, max drawdown 1.878151% (turnover 1.146023 — 2.5x
[[tsmom-spy-qqq]]'s 0.465489). **Worse than the ungated baseline on both
gate metrics**, not better. OOS holdout (trailing 25%, split
2022-09-29): in-sample Sharpe 0.610596, OOS Sharpe 0.808868 — again
improves on in-sample, so this isn't an overfit result, just a
structurally worse one throughout. Fold Sharpes: `[0.0, 1.225, 1.208,
-0.97, 0.021, 1.578, 1.201, 1.342, -2.172, 1.27, 1.2, 0.503]` — mixed
against tsmom-spy-qqq's recorded folds, mostly flat-to-worse (fold 4:
1.237 -> 0.021; fold 8: -1.223 -> -2.172), one clearly better (fold 5:
0.179 -> 1.578).

Falsification check (raw signal, `scripts/tsmom_vol_accel_backtest.py`),
directly against tsmom-spy-qqq's recorded numbers:

| window | symbol | tsmom-vol-accel flat % | tsmom-spy-qqq flat % |
|---|---|---|---|
| COVID crash | SPY | 48.6% | 0.0% |
| COVID crash | QQQ | 45.7% | 0.0% |
| 2022 bear market | SPY | 48.0% | 48.0% |
| 2022 bear market | QQQ | 52.0% | 52.0% |

**The specific mechanism claim is confirmed, not falsified**: the gate
materially increased flat-time during the COVID crash (0% -> ~47%),
exactly as designed — a fast vol-ratio check *can* react to a shock
inside tsmom's own 12-month blind spot. The 2022 window is unchanged
because tsmom's own signal already handled that slow grind; the gate
had nothing to add there, and correctly added nothing.

But the aggregate result is worse, not better. The gate isn't free: more
than doubling turnover (0.465 -> 1.146) means it's also closing and
reopening on ordinary volatile-but-not-crisis weeks throughout the whole
sample, not just around COVID — each of those round-trips pays fees and
slippage, and evidently costs more in aggregate than the COVID-window
protection is worth. The mechanism does what it claims; it just isn't a
net-positive trade at this threshold/window combination.

## Lifecycle history

- 2026-07-21 — created at `research` — single-variable follow-up to
  [[tsmom-spy-qqq]], adding one independent vol-acceleration gate aimed
  directly at that strategy's documented COVID-crash blind spot;
  vol_short_window/vol_long_window/vol_accel_threshold fixed before any
  backtest run, not searched. Includes `stop_loss_cooldown_sessions: 10`
  (Option C) from the start per [[stop-loss-rearm-coupling]].
- 2026-07-21 — retired — Sharpe 0.533888 / Sortino 0.872186, both worse
  than [[tsmom-spy-qqq]]'s ungated 0.813366/1.216489, and well short of
  the 1.0/1.2 gate. The pre-registered falsification test passed on its
  own narrow terms — COVID-window flat time rose from 0% to ~47% on both
  symbols, so the gate genuinely does react to a shock inside tsmom's
  blind spot — but turnover more than doubled (0.465 -> 1.146), and the
  added whipsaw cost from the gate firing on ordinary volatile-but-not-
  crisis weeks throughout the sample outweighs the COVID-window benefit.
  Worth separating cleanly: the *mechanism* claim (a fast vol-ratio check
  can out-react a 12-month trailing return) is validated; the *trade*
  (is it worth doing at this threshold) is not. Not a parameter-tuning
  target on this sample (threshold/windows were fixed before running,
  not searched) — if this axis gets revisited, the natural next lever is
  reducing whipsaw cost directly (e.g. a cooldown/hysteresis band around
  the gate) rather than re-fitting the threshold to this result.
