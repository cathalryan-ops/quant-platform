---
type: strategy
created: 2026-07-22
---

# TSMOM — TLT/GLD

Direct follow-up to [[tsmom-ms-shift-dualmom-blend]]'s retirement: that
3rd-leg attempt (dual-momentum-equity-bond-gold) turned out more
correlated with tsmom-spy-qqq (0.5852) than tsmom and ms-shift are with
each other (0.5522), because dual-momentum's cross-sectional ranking
reuses tsmom's own lookback=252/skip=21 logic on SPY as one of its three
candidates. This strategy tests whether a third leg that shares zero
symbols with the existing blend — not just a different ranking of an
overlapping basket — behaves differently.

## Hypothesis

[[time-series-momentum]], completely unmodified (same `lookback=252`,
`skip=21` as [[tsmom-spy-qqq]]), applied to TLT (20+ year Treasuries) and
GLD (gold) instead of SPY/QQQ, each scored independently — absolute
momentum per symbol, no cross-sectional ranking against each other or
against equities (structurally distinct from
[[dual-momentum-equity-bond-gold]], which ranks SPY/TLT/GLD against each
other and only ever holds one at a time). If trailing-return persistence
is a genuine feature of trending markets generally, not something specific
to SPY/QQQ's equity-beta regime, the same construction should show some
edge on rate-cycle (TLT) and safe-haven/inflation-cycle (GLD) trends too —
and because these are different risk drivers with a different macro
calendar than equities, any edge found should be meaningfully less
correlated with tsmom-spy-qqq/ms-shift-spy-high-displacement than
dual-momentum turned out to be.

Not a new mechanism and not a new parameterization — same signal class
(`strategies/tsmom_spy_qqq.py:Signal`) reused directly on a different
universe, the same precedent as [[tsmom-btc-eth]] (which needed a thin
wrapper only for the crypto calendar-day conversion; TLT/GLD are on the
standard equity trading calendar, so no wrapper is needed at all here).

**Killed if:** walk-forward Sharpe (2016-2024, 12 folds, 5 bps fees + 5 bps
slippage) fails to clear the standing 1.0/1.2 gate — same bar as every
other strategy in this vault, no special exception. **Also checked:**
pairwise correlation with tsmom-spy-qqq and ms-shift-spy-high-displacement,
compared directly against dual-momentum's own correlation numbers
(0.5852 / correlation to ms-shift not separately measured) to test whether
sharing zero symbols actually buys lower correlation than dual-momentum's
shared-candidate-basket construction did.

## Mechanism

See [[time-series-momentum]]. Same causal story as tsmom-spy-qqq — trend
persistence from slow information diffusion, institutional flow inertia,
and disposition-effect-driven underreaction — applied to different
underlying markets. Who loses: the same trend-agnostic or contrarian
counterparties tsmom-spy-qqq's writeup already names, but operating in
rates and gold markets instead of equities — e.g. investors rebalancing
mechanically against a persistent bond rally, or gold's own mean-reversion
crowd fading a sustained inflation-driven uptrend.

## Falsification test

Same construction as tsmom-spy-qqq's own falsification logic: report
per-symbol time-in-market and fold-level Sharpe alongside the aggregate,
so a near-miss driven by one symbol carrying the other is visible rather
than hidden in a blended average. Also report the correlation check above
directly, since the entire point of this strategy is testing whether a
zero-symbol-overlap third leg diversifies better than dual-momentum's
shared-basket one did.

## Manifest

```strategy_manifest
{
  "schema_version": "1.0.0",
  "id": "tsmom-tlt-gld",
  "wiki_page": "brain/wiki/strategies/tsmom-tlt-gld.md",
  "market": "us_equities",
  "family": "swing",
  "universe": ["TLT", "GLD"],
  "hypothesis": "Time-series momentum (lookback=252, skip=21, unmodified from tsmom-spy-qqq) applied independently to TLT and GLD, scored per-symbol with no cross-sectional ranking. Tests whether trend persistence generalizes beyond equities to rate-cycle and safe-haven/inflation-cycle regimes, and whether a third blend leg sharing zero symbols with tsmom-spy-qqq/ms-shift-spy-high-displacement diversifies better than dual-momentum-equity-bond-gold's shared-SPY-candidate construction did. Killed if walk-forward Sharpe does not clear the standing 1.0/1.2 gate.",
  "signal_spec": { "language": "python", "entrypoint": "strategies/tsmom_spy_qqq.py:Signal" },
  "risk": { "max_position_pct": 5.0, "stop_loss_pct": 2.0, "stop_loss_cooldown_sessions": 10 },
  "lifecycle": "retired",
  "scorecard": {
    "sharpe_wf": 0.173042, "sortino_wf": 0.402854, "max_drawdown_bt": 2.314457,
    "sharpe_paper": null, "max_drawdown_paper": null, "pnl_live": null,
    "rank": null
  }
}
```

## Evidence

Real walk-forward backtest (2016-01-01 to 2024-12-31, `folds=12`, real
16-symbol Alpaca data restricted to TLT/GLD,
`data/results/tsmom-tlt-gld/`, `scripts/tsmom_tlt_gld_backtest.py`):
Sharpe 0.173042, Sortino 0.402854, max drawdown 2.314457%, turnover
0.594002 — a clear miss versus the 1.0/1.2 gate, roughly the same order
of magnitude as [[tsmom-btc-eth]]'s 0.219 (same mechanism, different
non-equity market). Fold Sharpes: `[0.0, -0.138, 0.995, -2.818, 1.828,
1.297, -1.114, 0.217, -0.971, 0.01, 1.584, 1.186]` — noisy, five of
twelve folds negative. OOS holdout (trailing 25%, split 2022-09-29):
in-sample Sharpe 0.204994, OOS Sharpe 0.947444 — improves on in-sample
(PASSED), so this is not an in-sample-only artifact, just a genuinely
weak edge. Per-symbol time-in-market: TLT long 29.5% of sessions, GLD
58.6% — both trade real time long, not degenerate to always-flat.

**Falsification check — the actual point of this strategy — is the
striking result:** Pearson correlation between tsmom-tlt-gld's daily
returns and tsmom-spy-qqq's is **0.0051**, and vs.
ms-shift-spy-high-displacement's is **0.0689** — both essentially zero,
dramatically lower than dual-momentum-equity-bond-gold's 0.5852/(implied
higher) correlation to the same two legs. This confirms the hypothesis
directly: sharing zero symbols with the existing blend legs buys
genuinely independent exposure, unlike dual-momentum's shared-SPY-
candidate construction. Unlike [[mean-reversion-spy-qqq]] or
`turn-of-month-spy-qqq` (confirmed mechanism-level nulls — forward
returns statistically indistinguishable from random), this signal has a
real, if weak, positive edge (Sharpe 0.173 > 0, OOS improves on
in-sample) — the profile diversification theory says is most likely to
help a blend precisely because near-zero correlation lets even a weak
edge add expected return without proportionally adding variance.
Retired as a standalone strategy per the standing gate, but immediately
tested as a blend leg — see [[tsmom-ms-shift-tltgld-blend]].

## Lifecycle history

- 2026-07-22 — created at `research` — direct follow-up to
  [[tsmom-ms-shift-dualmom-blend]]'s retirement; reuses tsmom-spy-qqq's
  signal class unmodified on a zero-symbol-overlap universe (TLT/GLD), no
  new parameters to fix. Includes `stop_loss_cooldown_sessions: 10`
  (Option C) from the start.
- 2026-07-22 — retired — Sharpe 0.173042, a clear miss on the standalone
  gate, but the pre-registered correlation check is the real finding:
  0.0051 vs tsmom-spy-qqq and 0.0689 vs ms-shift-spy-high-displacement —
  near-zero, confirming a zero-symbol-overlap leg genuinely diversifies
  where dual-momentum's shared-basket construction (0.5852 vs tsmom)
  didn't. The edge is real but weak (OOS improves on in-sample, both
  symbols trade real time long), unlike the confirmed nulls
  (mean-reversion, turn-of-month) already ruled out as blend candidates.
  Immediately tested as a blend leg per this page's own falsification
  test — see [[tsmom-ms-shift-tltgld-blend]] for the result.