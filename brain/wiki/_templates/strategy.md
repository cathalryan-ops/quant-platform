---
type: strategy
created: YYYY-MM-DD
---

# <Strategy Name>

## Hypothesis

One paragraph, falsifiable. State the edge and the number that would kill it.

## Mechanism

Why should this edge exist? Who is on the other side and why do they lose?
Link the [[concept pages]] that carry the underlying ideas.

## Falsification test

The cheapest experiment that could disprove the hypothesis.

## Manifest

```strategy_manifest
{
  "schema_version": "1.0.0",
  "id": "<kebab-case-id>",
  "wiki_page": "brain/wiki/strategies/<this-file>.md",
  "market": "us_equities",
  "family": "ms_shift",
  "universe": ["SPY"],
  "hypothesis": "<same claim, one paragraph>",
  "signal_spec": { "language": "python", "entrypoint": "strategies/<file>.py:Signal" },
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

Links to result files and [[postmortem pages]] as they accumulate.

## Lifecycle history

- YYYY-MM-DD — created at `research` — <source link>
