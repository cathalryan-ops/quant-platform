---
type: strategy
created: 2026-07-21
---

# 52-Week High Proximity — SPY/QQQ

A structurally different construction from every prior strategy in this
vault, including [[tsmom-spy-qqq]]: a ratio of price to its own rolling
*maximum*, not a trailing return, not a swing/displacement break, not a
realized-vol statistic, not a calendar position.

## Hypothesis

[[fifty-two-week-high-effect]] (George & Hwang 2004): price proximity to
its own trailing 252-session high predicts near-term continuation, via
anchoring bias rather than [[time-series-momentum]]'s underreaction-to-
flow story. Long-only, scored independently per symbol: long while
today's close is within `nearness_threshold` of its trailing
`lookback`-session high, flat otherwise.

Parameters fixed before any backtest ran: `lookback=252` (the standard
trailing 52-week/12-month window, matching TSMOM's own lookback for
internal consistency, not re-derived from this dataset).
`nearness_threshold=0.95` — within 5% of the trailing high, a common
practitioner definition of "near a 52-week high" and a round number, not
fit to this sample's outcome.

**Killed if:** walk-forward Sharpe (2016-2024, 12 folds, 5 bps fees + 5
bps slippage) fails to clear the standing gate (Sharpe ≥1.0, Sortino
≥1.2). **Also checked, not just the aggregate number:** how correlated is
this signal's daily weight with [[tsmom-spy-qqq]]'s raw signal? If
they're nearly identical (near-100% overlap), this isn't really an
independent test of a different mechanism — it's the same bet on the same
underlying uptrends measured two ways, and a similar result would carry
much less information than a genuinely independent replication would.

## Mechanism

See [[fifty-two-week-high-effect]]. Anchoring/reference-point bias:
investors mentally anchor to a security's 52-week high as a valuation
reference and are reluctant to bid above it regardless of fundamentals,
producing gradual underreaction to genuinely positive news near that
level; once price holds near or breaks the anchor, the backlog resolves
as continued drift. Distinct causal claim from TSMOM's crowd-driven
trend-following/flow story, even though both are "long in uptrends"
signals in practice.

## Falsification test

Compare this signal's raw daily weight directly against
[[tsmom-spy-qqq]]'s raw daily weight (same universe, same period): report
the fraction of sessions where the two agree. High agreement doesn't
invalidate the result, but it does mean a similar Sharpe here is a weak
independent confirmation, not two separate pieces of evidence — worth
knowing before reading too much into whichever number comes out.

## Manifest

```strategy_manifest
{
  "schema_version": "1.0.0",
  "id": "52wk-high-spy-qqq",
  "wiki_page": "brain/wiki/strategies/52wk-high-spy-qqq.md",
  "market": "us_equities",
  "family": "swing",
  "universe": ["SPY", "QQQ"],
  "hypothesis": "Price proximity to its own trailing 252-session high predicts near-term continuation (George & Hwang 2004 anchoring-bias mechanism); long-only, scored independently per symbol, long while close is within 5% of the trailing high. Killed if walk-forward Sharpe does not clear 1.0.",
  "signal_spec": { "language": "python", "entrypoint": "strategies/high52_spy_qqq.py:Signal" },
  "risk": { "max_position_pct": 5.0, "stop_loss_pct": 2.0, "stop_loss_cooldown_sessions": 10 },
  "lifecycle": "retired",
  "scorecard": {
    "sharpe_wf": 0.625403, "sortino_wf": 1.052264, "max_drawdown_bt": 2.255647,
    "sharpe_paper": null, "max_drawdown_paper": null, "pnl_live": null,
    "rank": null
  }
}
```

## Evidence

Real walk-forward backtest (2016-01-01 to 2024-12-31, `folds=12`, real
SPY+QQQ Alpaca data, `data/results/52wk-high-spy-qqq/`): Sharpe
0.625403, Sortino 1.052264, max drawdown 2.255647%, turnover 1.055683 —
more than double [[tsmom-spy-qqq]]'s ungated 0.465489. OOS holdout
(trailing 25%, split 2022-09-29): in-sample Sharpe 0.625067, OOS Sharpe
1.131151 — improves on in-sample, consistent with nearly every strategy
in this vault's momentum-adjacent line (the later part of the sample
appears broadly favorable to long-biased trend strategies, not something
specific to this signal). Fold Sharpes: `[0.0, 2.072, 1.392, -0.735,
-0.93, 1.804, 1.272, 1.538, -2.664, 1.579, 1.476, 0.701]`.

Falsification check (raw signal, `scripts/high52_backtest.py`) — daily
agreement with tsmom-spy-qqq's raw signal on the same bars: SPY 81.9%
agreement (57.4% both-long), QQQ 78.6% agreement (55.4% both-long).
**Moderate-to-high overlap, not identical.** The two mechanisms mostly
agree — expected, since both are fundamentally "is this an uptrend"
signals — but disagree roughly one session in five, so this is a
partially, not fully, independent replication. Read in that light: a
Sharpe (0.625) clearly below tsmom-spy-qqq's 0.813 isn't just noise
around the same bet — the disagreement sessions net out worse than
tsmom's own signal, and turnover more than doubles tsmom's despite no
holding-period logic being added. The price-to-rolling-max ratio appears
to flicker across its 0.95 threshold more often near turning points than
a trailing-return sign flip does, adding cost without adding edge.

## Lifecycle history

- 2026-07-21 — created at `research` — structurally different
  construction from every prior strategy (price-to-rolling-max ratio, not
  a trailing return), specifically chosen to test whether a different
  causal mechanism (anchoring bias) produces a different result than
  [[time-series-momentum]] on the same universe; lookback/threshold fixed
  before any backtest run, not searched. Includes
  `stop_loss_cooldown_sessions: 10` (Option C) from the start per
  [[stop-loss-rearm-coupling]].
- 2026-07-21 — retired — Sharpe 0.625403 / Sortino 1.052264, short of
  the 1.0/1.2 gate and meaningfully below tsmom-spy-qqq's 0.813366/
  1.216489 (not a comparable near-miss). Raw-signal agreement with
  tsmom-spy-qqq is moderate-to-high (~80%), so this isn't a clean
  independent replication of the momentum result — it's a related but
  distinct bet that happens to net out worse, with turnover more than
  double tsmom's despite an identical no-state-machine design, suggesting
  the price-to-rolling-max construction chatters near its threshold more
  than a trailing-return sign flip does. Not a parameter-tuning target;
  no further 52-week-high variant flagged as a next step.
