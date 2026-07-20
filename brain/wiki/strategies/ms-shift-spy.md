---
type: strategy
created: 2026-07-19
---

# MS Shift SPY

## Hypothesis

On daily SPY/QQQ charts, a [[market-structure-shift]] confirmed by
[[displacement]] (close beyond the broken swing point with a range ≥ 1.5×
20-day ATR) is followed by multi-day continuation in the break direction
often enough that a long-only implementation clears costs. **Killed if
walk-forward Sharpe over 2018–present daily bars is below 1.0 after 5 bps
fees + 5 bps slippage.**

## Mechanism

Traders anchored to the prior trend are forced out when structure breaks;
their exits fuel continuation. Displacement filters for breaks driven by
large participants rather than noise
([source](../../raw/sample-market-structure-primer.md)). We lose if the
edge is arbitraged at daily granularity or if displacement is not
predictive out of sample.

## Falsification test

Backtest the harness's walk-forward splits on SPY+QQQ daily bars with the
displacement filter on vs off. If filtered Sharpe ≤ unfiltered Sharpe, the
displacement premise is false regardless of overall profitability.

## Manifest

```strategy_manifest
{
  "schema_version": "1.0.0",
  "id": "ms-shift-spy-v1",
  "wiki_page": "brain/wiki/strategies/ms-shift-spy.md",
  "market": "us_equities",
  "family": "ms_shift",
  "universe": ["SPY", "QQQ"],
  "hypothesis": "A daily market-structure shift with displacement (close beyond the broken swing with range >= 1.5x 20-day ATR) precedes multi-day continuation; killed if walk-forward Sharpe 2018-present < 1.0 after 5 bps fees + 5 bps slippage.",
  "signal_spec": { "language": "python", "entrypoint": "strategies/ms_shift_spy.py:Signal" },
  "risk": { "max_position_pct": 5.0, "stop_loss_pct": 2.0 },
  "lifecycle": "retired",
  "scorecard": {
    "sharpe_wf": 0.674305, "sortino_wf": 0.963402, "max_drawdown_bt": 1.434952,
    "sharpe_paper": null, "max_drawdown_paper": null, "pnl_live": null,
    "rank": null
  }
}
```

## Evidence

- Source primer: [market structure basics](../../raw/sample-market-structure-primer.md)
- Concepts: [[market-structure-shift]], [[displacement]]
- Postmortems: [[ms-shift-spy-example]]
- Walk-forward backtest (2016-01-01–2024-12-31, 5 bps fees + 5 bps slippage per side, manually recorded — see Lifecycle history for reproducibility caveat): Sharpe 0.674305, Sortino 0.963402, max drawdown 1.434952%; failed the backtest→paper gate on Sharpe and Sortino.

## Lifecycle history

- 2026-07-19 — created at `research` — proposed from seeded primer (P3 dry run)
- 2026-07-20 — retired — Manually recorded walk-forward backtest (2016-01-01 to 2024-12-31, 9 years, 5 bps fees + 5 bps slippage per side) failed the backtest→paper gate in `contracts/promotion_thresholds.toml`: Sharpe 0.674305 vs min 1.0 (missed by 0.325695), Sortino 0.963402 vs min 1.2 (missed by 0.236598). max_drawdown_pct 1.434952% was well within the 15.0% cap, so drawdown was not the failure driver. Per-fold walk-forward Sharpes, chronological: [0.313, 0.428, 1.45, -0.32, 1.45]. Flagging as an observation, not a conclusion: the spread across folds (two folds above 1.4, one negative) suggests the edge may be regime-dependent rather than uniformly absent; a follow-up research question on which calendar periods those folds cover is being filed separately — no speculation on specific years/events here. Reproducibility note: this result is NOT reproducible from this repo's `data/` — the fetched SPY+QQQ parquet snapshot is gitignored and exists only in the operator's environment (a GitHub Codespace run against real Alpaca API credentials). It was recorded manually rather than through the automated ranker pipeline precisely because fabricating a `data_snapshot.content_hash` this repo can't verify would undermine the platform's reproducibility guarantee.
