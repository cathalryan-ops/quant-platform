---
type: strategy
created: 2026-07-22
---

# MS-Shift / TSMOM Blend — BTC/USD, ETH/USD

Crypto-native analog of [[tsmom-ms-shift-blend]] (this vault's best
equity result, Sharpe 0.884266 at proposal time, since surpassed by
[[tsmom-ms-shift-tltgld-blend]] at 0.989632). Direct follow-up to
[[ms-shift-btc-eth]]'s falsification check: correlation to
[[tsmom-btc-eth]] is 0.4319 and raw signal agreement only 45.9-50.4% —
moderate correlation and near-coin-flip agreement, a stronger
independence signature than the equity blend's own legs had at inception
(0.5522 correlation). Both crypto legs individually miss the 1.0/1.2 gate
(ms-shift-btc-eth 0.559667, tsmom-btc-eth 0.21921), but the equity
precedent showed two near-miss, moderately-correlated legs can combine to
beat both.

## Hypothesis

[[signal-blending]]: average ms-shift-btc-eth's and tsmom-btc-eth's
position weights 50/50 (fixed a priori, unchanged from the equity blend's
own discipline), both legs' own parameters carried over unchanged from
their individually-retired strategies. Unlike the SPY/QQQ/TLT/GLD blend
line, no union-universe composition is needed — both legs already operate
on the identical BTC/USD, ETH/USD pair, so this reuses
`tsmom_ms_shift_blend.py`'s exact architecture (simple weighted average,
same two symbols) rather than the 3-way blends' subset-composition
pattern.

If the moderate correlation and near-coin-flip signal agreement translate
into the same kind of diversification lift the equity blend showed, the
combined Sharpe should exceed both legs' individual current-engine
numbers, and — given ms-shift-btc-eth alone is already the strongest
single crypto result (0.559667, only 44% short of the gate) — this is the
most plausible remaining path to a crypto strategy actually clearing the
gate, or coming close.

**Killed if:** walk-forward Sharpe does not clear ms-shift-btc-eth's own
current-engine Sharpe (re-measured fresh in this run) or the standing
1.0/1.2 gate — same structure as every blend kill criterion in this
vault (must beat the stronger individual leg, not just the average).
**Also checked:** does the blend show a different, less asymmetric
exposure profile across the FTX-collapse shock and 2022 bear decline than
either leg alone, given the two legs' documented divergent per-symbol
behavior during those windows.

## Mechanism

See [[signal-blending]], [[market-structure-shift]]/[[displacement]], and
[[time-series-momentum]]. No new causal claim about either underlying
mechanism on crypto — both were independently validated as real (if
individually insufficient) edges on this data via their own retirements.
The only new claim is the same portfolio-construction one the equity
blend tested: two edges with moderate correlation and low day-to-day
agreement should partially offset each other's idiosyncratic drawdowns
when held together.

## Falsification test

Compute Pearson correlation of the two legs' daily portfolio return
streams (each re-run standalone under identical current-engine risk
settings) over the full 2021-2024 crypto sample — already established at
0.4319 on [[ms-shift-btc-eth]]'s own page, re-confirmed here for the
blend's own record — alongside the blend's Sharpe/Sortino/drawdown/
turnover compared directly against both legs measured fresh in the same
run.

## Manifest

```strategy_manifest
{
  "schema_version": "1.0.0",
  "id": "ms-shift-tsmom-blend-btc-eth",
  "wiki_page": "brain/wiki/strategies/ms-shift-tsmom-blend-btc-eth.md",
  "market": "crypto",
  "family": "ms_shift",
  "universe": ["BTC/USD", "ETH/USD"],
  "hypothesis": "Averaging ms-shift-btc-eth's and tsmom-btc-eth's position weights 50/50 (both unchanged, blend_weight=0.5 fixed a priori), on the strength of their moderate correlation (0.4319) and near-coin-flip raw signal agreement (45.9-50.4%). Killed if walk-forward Sharpe does not clear ms-shift-btc-eth's own current-engine Sharpe or the standing 1.0/1.2 gate.",
  "signal_spec": { "language": "python", "entrypoint": "strategies/ms_shift_tsmom_blend_btc_eth.py:Signal" },
  "risk": { "max_position_pct": 5.0, "stop_loss_pct": 2.0, "stop_loss_cooldown_sessions": 10 },
  "lifecycle": "retired",
  "scorecard": {
    "sharpe_wf": 0.406965, "sortino_wf": 0.725072, "max_drawdown_bt": 2.657305,
    "sharpe_paper": null, "max_drawdown_paper": null, "pnl_live": null,
    "rank": null
  }
}
```

## Evidence

Real walk-forward backtest (2021-01-01 to 2024-12-31, `folds=8`, real
BTC/USD+ETH/USD Alpaca crypto data,
`data/results/ms-shift-tsmom-blend-btc-eth/`,
`scripts/ms_shift_tsmom_blend_btc_eth_backtest.py`), run alongside fresh
current-engine standalone re-runs of both legs:

| | Sharpe | Sortino | Max DD % | Turnover |
|---|---|---|---|---|
| ms-shift-btc-eth (fresh re-run) | 0.559667 | 0.907426 | 2.741119 | 1.640095 |
| tsmom-btc-eth (fresh re-run) | 0.21921 | 0.478232 | 3.680552 | 0.76819 |
| **ms-shift-tsmom-blend-btc-eth** | **0.406965** | **0.725072** | **2.657305** | **1.110624** |

**This blend does not clear its own kill criterion — it is worse than
ms-shift-btc-eth alone, not better**, in sharp contrast to the equity
blend's result. Fold-by-fold, the mechanism is legible: in the three
folds where tsmom-btc-eth was exactly flat (0.0 Sharpe, no position),
the blend exactly reproduces ms-shift-btc-eth's own fold Sharpe at half
size (identical values: -0.508, 0.747, -0.251), confirming the blend
arithmetic is doing what it should. In the remaining five folds,
averaging in tsmom-btc-eth pulled the blend below ms-shift-btc-eth alone
in four of them (most sharply fold 3: ms-shift -0.502 alone vs. blend
-1.543, both legs negative that fold and averaging didn't help), and
above it in only one (fold 7: 0.941 alone vs. 1.74 blended).

**Why this differs from the equity blend, despite comparable correlation
(0.4319 here vs. tsmom-spy-qqq/ms-shift's 0.5522 on equities):** the two
equity legs were near-equal in individual strength (0.813 vs. 0.759, a
7% gap) when they were blended 50/50. Here the two legs are far apart
(0.559667 vs. 0.21921 — ms-shift-btc-eth is **2.55x** tsmom-btc-eth's
Sharpe). Fixed 50/50 weighting between two legs that unequal in strength
drags the average down more than moderate correlation can compensate
for — diversification reduces variance, but it can't manufacture the
weaker leg's missing expected return. **Refines the finding from
[[blend-leg-search-2026-07-22]]:** correlation alone is not sufficient
for equal-weight blending to help; the legs also need comparable
individual strength, or the weighting needs to reflect the imbalance
(a fitted weight is exactly the kind of post-hoc tuning this vault's
discipline avoids on a small, already-tested sample, so not attempted
here).

OOS holdout (trailing 25%, split 2024-01-02): in-sample Sharpe 0.17432,
OOS Sharpe 1.507065 — improves substantially, same 2024-bull-year caveat
as every crypto OOS result in this vault. Not read as a robustness
signature given the short, single-regime holdout window.

## Lifecycle history

- 2026-07-22 — created at `research` — direct follow-up to
  [[ms-shift-btc-eth]]'s falsification check; blend_weight fixed at 0.5
  before any backtest run, both component signals' own parameters
  carried over unchanged. Includes `stop_loss_cooldown_sessions: 10`
  (Option C) from the start.
- 2026-07-22 — retired — Sharpe 0.406965, below ms-shift-btc-eth's own
  0.559667 — fails its kill criterion cleanly, the opposite outcome from
  the equity blend despite comparable leg correlation (0.4319 vs.
  0.5522). Root cause identified fold-by-fold: the two legs are 2.55x
  apart in individual strength (0.559667 vs. 0.21921), and fixed 50/50
  weighting between unequal-strength legs dilutes the stronger leg's
  return more than moderate correlation compensates for in variance
  reduction. Refines [[blend-leg-search-2026-07-22]]'s finding:
  correlation is necessary but not sufficient for equal-weight blending
  to help — comparable individual leg strength matters too. Not a
  parameter-tuning target: no weight search attempted (would be fitting
  a blend ratio to this exact small crypto sample, the overfitting
  pattern flagged repeatedly in this vault). Closes the crypto-blend
  question for now: on this data, crypto momentum does not benefit from
  the same blending lever that worked on equities, because the two
  available crypto-native mechanisms aren't comparably strong.