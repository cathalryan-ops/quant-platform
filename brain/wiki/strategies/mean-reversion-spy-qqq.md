---
type: strategy
created: 2026-07-20
---

# Mean Reversion SPY/QQQ

A genuinely different mechanism from [[ms-shift-spy]] — not a parameter
variant. Where `ms_shift` buys confirmed continuation after a structure
break, this buys an outsized single-day drop and holds for a short fixed
horizon, with no structure/swing/displacement logic at all.

## Hypothesis

A close-to-close daily return at least `drop_mult` (2.0) standard
deviations below the trailing `lookback`-day (20) mean is followed by
short-horizon (`hold_days`=5 sessions) reversion often enough to clear
costs on SPY/QQQ. Parameters were chosen before any backtest was run —
20 trading days (~1 month) is a standard realized-volatility window, 2.0σ
is a conventional "meaningfully extreme, not vanishingly rare" threshold,
5 sessions (~1 week) is a short horizon consistent with the mean-reversion
premise (a longer hold risks re-testing the momentum regime `ms_shift`
already covers). None of these were tuned against this dataset.

**Killed if:** walk-forward Sharpe (same 2016-2024 window, 12 folds, 5 bps
fees + 5 bps slippage, as ms-shift-spy) fails to clear the same
`backtest_to_paper` gate in `contracts/promotion_thresholds.toml` (Sharpe
≥1.0, Sortino ≥1.2) already used for this strategy family — no separate,
easier bar for this hypothesis. **Also killed** if the mechanism-level
falsification test below shows no real reversion effect, even if the
Sharpe number alone looks passable.

## Mechanism

Overreaction / liquidity-provision premise: a single-day move well beyond
recent realized volatility is more often a liquidity-driven overshoot
(forced selling, a stale limit order cascade, a headline-driven air pocket
without a fundamental repricing) than the start of a new sustained trend
— the opposite operating assumption to `ms_shift`'s continuation premise.
Whoever is on the other side of the reversion trade is the panic seller
who sold *because* of the drop, not because of new information that
should persist.

We lose if: (a) the "extreme move" is actually information, not noise
(the drop reflects real repricing that continues), (b) the effect is
arbitraged away at daily granularity by the time this signal could act on
it, or (c) SPY/QQQ specifically don't exhibit this at the 2σ/20-day
parameterization tested.

## Falsification test

Compare the mean forward return over the `hold_days` window following a
triggered entry against the unconditional mean forward return over
randomly sampled `hold_days` windows of the same series. If the
triggered-entry mean is not clearly above the random baseline, the
reversion premise is false regardless of what the aggregate walk-forward
Sharpe says (a Sharpe that survives purely on cost/sizing mechanics, not a
real reversion effect, shouldn't be trusted).

## Manifest

```strategy_manifest
{
  "schema_version": "1.0.0",
  "id": "mean-reversion-spy-qqq",
  "wiki_page": "brain/wiki/strategies/mean-reversion-spy-qqq.md",
  "market": "us_equities",
  "family": "swing",
  "universe": ["SPY", "QQQ"],
  "hypothesis": "A close-to-close daily return >= 2.0 standard deviations below the trailing 20-day mean is followed by reversion over the next 5 sessions often enough to clear costs; killed if walk-forward Sharpe 2016-2024 < 1.0 after 5 bps fees + 5 bps slippage (same gate as ms-shift-spy), or if the mechanism-level forward-return falsification test shows no real reversion effect.",
  "signal_spec": { "language": "python", "entrypoint": "strategies/mean_reversion_spy_qqq.py:Signal" },
  "risk": { "max_position_pct": 5.0, "stop_loss_pct": 2.0 },
  "lifecycle": "retired",
  "scorecard": {
    "sharpe_wf": 0.02269, "sortino_wf": 0.356024, "max_drawdown_bt": 2.597472,
    "sharpe_paper": null, "max_drawdown_paper": null, "pnl_live": null,
    "rank": null
  }
}
```

## Evidence

Real walk-forward backtest (2016-01-01 to 2024-12-31, `folds=12`, real
SPY+QQQ Alpaca data, `data/results/mean-reversion-spy-qqq/`): Sharpe
0.02269, Sortino 0.356024, max drawdown 2.597472%, turnover 1.701833 (far
higher than ms-shift-spy's ~0.2-0.4 — this signal trades much more often).
Per-fold Sharpes, chronological: [-0.054, 1.237, -0.627, -1.649, 1.016,
-0.591, -0.216, 0.572, -2.071, -0.102, 2.432, 0.326] — noisy and
mostly negative, no consistent edge. OOS holdout (trailing 25%, split
2022-09-29): in-sample Sharpe was itself negative (-0.470061), so the OOS
check rejects by construction (no positive edge to validate out-of-sample
in the first place).

**Mechanism-level falsification test (pre-registered above) also fails
the hypothesis directly:** triggered-entry mean forward return over the
5-session hold vs. a 5000-sample random-start bootstrap of same-length
forward returns, same series — SPY: 65 triggers, trigger mean +0.214% vs.
random baseline +0.223% (z ≈ -0.03, indistinguishable from random). QQQ:
68 triggers, trigger mean +0.076% vs. random baseline +0.401% (z ≈ -0.95,
if anything worse than random). No detectable reversion effect at this
parameterization — the hypothesis is falsified at the mechanism level,
independent of the aggregate Sharpe number.

Same reproducibility caveat as ms-shift-spy: `data/` is gitignored, this
result is manually recorded via the pinned parquet snapshot in this
Codespace, not reproducible from this repo alone.

## Lifecycle history

- 2026-07-20 — created at `research` — proposed as a structurally distinct
  alternative to [[ms-shift-spy]]/[[ms-shift-spy-high-displacement]] after
  both retired and [[stop-loss-rearm-coupling]] validated the re-arm fix
  without resurrecting either strategy's promotion case; parameters
  (lookback=20, drop_mult=2.0, hold_days=5) fixed before any backtest run,
  not searched.
- 2026-07-20 — retired — Both pre-registered falsification criteria
  triggered. Walk-forward Sharpe 0.02269 (vs. min 1.0) and Sortino
  0.356024 (vs. min 1.2) — nowhere close to the gate, and OOS-rejected on
  top of that (in-sample Sharpe itself negative). More importantly, the
  mechanism-level test shows no real reversion effect: triggered-entry
  forward returns are statistically indistinguishable from a random
  baseline on both SPY (z≈-0.03) and QQQ (z≈-0.95). This isn't a near-miss
  worth parameter-searching around — there's no detectable edge at the
  mechanism level to tune toward. A genuinely different hypothesis is the
  right next step, not a lookback/drop_mult/hold_days sweep on this one.
