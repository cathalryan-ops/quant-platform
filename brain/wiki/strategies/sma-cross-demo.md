---
type: strategy
created: 2026-07-19
---

# SMA Cross Demo

The trivial reference strategy used by the integration test (P11) to drive
the full loop end-to-end. Not a real edge — a wire that touches every seam.

## Hypothesis

A 20/50-day SMA crossover on SPY captures trend persistence. **Killed if
walk-forward Sharpe is below the backtest→paper threshold** — which, on a
toy strategy, it usually is; that is fine. The point is that the loop
promotes or retires it *correctly*, not that it makes money.

## Mechanism

Trend-following: momentum persistence. The demo makes no claim to a durable
edge; see [[market-structure-shift]] for a real hypothesis.

## Falsification test

Run the harness; the ranker's threshold decision is the test.

## Manifest

```strategy_manifest
{
  "schema_version": "1.0.0",
  "id": "sma-cross-demo",
  "wiki_page": "brain/wiki/strategies/sma-cross-demo.md",
  "market": "us_equities",
  "family": "swing",
  "universe": [
    "SPY"
  ],
  "hypothesis": "A 20/50-day SMA crossover on SPY captures trend persistence; killed if walk-forward Sharpe is below the backtest-to-paper threshold.",
  "signal_spec": {
    "language": "python",
    "entrypoint": "strategies/sma_cross.py:Signal"
  },
  "risk": {
    "max_position_pct": 5.0,
    "stop_loss_pct": 2.0
  },
  "lifecycle": "research",
  "scorecard": {
    "sharpe_wf": -0.275672,
    "sortino_wf": -0.159256,
    "max_drawdown_bt": 1.240641,
    "sharpe_paper": 0.0,
    "max_drawdown_paper": 0.0,
    "pnl_live": null,
    "rank": 1
  }
}
```

## Evidence

Populated by the integration test run.

## Lifecycle history

- 2026-07-19 — created at `research` — P11 integration test seed
