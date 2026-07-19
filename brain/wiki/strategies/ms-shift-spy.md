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
  "lifecycle": "research",
  "scorecard": {
    "sharpe_wf": null, "sortino_wf": null, "max_drawdown_bt": null,
    "sharpe_paper": null, "max_drawdown_paper": null, "pnl_live": null,
    "rank": null
  }
}
```

## Evidence

- Source primer: [market structure basics](../../raw/sample-market-structure-primer.md)
- Concepts: [[market-structure-shift]], [[displacement]]

## Lifecycle history

- 2026-07-19 — created at `research` — proposed from seeded primer (P3 dry run)
