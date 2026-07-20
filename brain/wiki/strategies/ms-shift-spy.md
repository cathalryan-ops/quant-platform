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
- 2026-07-20 — retired (follow-up) — The filed follow-up (re-run at `folds=12`) came back and **falsified** the "2022 whipsaw" regime hypothesis by its own stated criterion: the folds spanning the original negative window (2022-01-04–2022-10-03: Sharpe 0.0; 2022-10-04–2023-07-05: Sharpe 0.613) are flat-to-positive, not negative — the original -0.32 fold does not reproduce at finer resolution and looks like a 5-way-split boundary artifact rather than a real regime effect. Overall Sharpe at 12 folds (0.657) is consistent with the original (0.674), so the retirement stands either way. Revised characterization: three folds clearly outperform (2019-10–2020-07: 2.086, COVID crash+recovery; 2020-07–2021-04: 1.292; 2023-07–2024-04: 1.7, AI rally) while the other nine sit in a mediocre 0.0–0.82 band — the edge looks concentrated in a few strong post-shock continuation windows rather than genuinely regime-conditional. Full breakdown and reasoning: [[ms-shift-spy-v1-fold-regime-hypothesis]] (`brain/raw/`).
- 2026-07-20 — engine gap closed, then structurally re-investigated — `risk.stop_loss_pct` is now actually enforced in both the Python backtester and Rust engines (previously validated for shape only). Plain enforcement made walk-forward Sharpe/Sortino *worse*, not better — root-caused to a re-arm/trend-persistence coupling bug, not a flaw in the stop level itself: see [[stop-loss-rearm-coupling]] for the full mechanism (QQQ stopped out 2022-12-05, locked out of the market until 2023-10-06, missing a +24% recovery the raw signal itself would have ridden). Fixed via a combined re-arm rule ("Option C") and validated out-of-sample: the true original re-arm design gets rejected by a 35%-degradation OOS gate on this exact fold (+74.0% degradation); Option C passes cleanly (-4.4%, OOS *better* than in-sample). This validates the fix structurally — it does not change this strategy's status. `passed_thresholds` remains `false` even with Option C (Sharpe ~0.63, still below the 1.0 minimum); this page stays `retired`.
