---
type: strategy
created: 2026-07-21
---

# Dual Momentum — Equities / Bonds / Gold

The second cross-sectional strategy in this vault, and the first to span
more than one asset class. [[sector-rotation]] ranks 10 members of the
*same* asset class (equity sectors) against each other, so it always
holds something — even in a broad market downturn, some sector is the
"least bad" relative leader. This strategy ranks SPY, TLT, and GLD —
equities, long bonds, and gold, three genuinely different risk regimes —
and adds [[time-series-momentum]]'s absolute floor on top of the
cross-sectional rank, so it can go to cash when nothing in the basket
actually looks good, not just own whatever is relatively least bad.

## Hypothesis

[[dual-momentum]]: each month, rank SPY/TLT/GLD by trailing 12-1 momentum
and hold the single relative leader — but only if that leader's own
trailing momentum is positive; otherwise cash. This composes
[[cross-sectional-momentum]] (already tested via [[sector-rotation]],
Sharpe 0.255, a clear miss) with [[time-series-momentum]] (already tested
via [[tsmom-spy-qqq]], Sharpe 0.813, this vault's best result) into a
flight-to-quality mechanism neither prior test could express alone:
sector-rotation's basket can't go flat (every candidate is equity risk),
and tsmom-spy-qqq's SPY/QQQ universe has no non-equity asset to rotate
into during an equity drawdown.

Parameters fixed before any backtest ran: `lookback=252`, `skip=21` —
identical to [[tsmom-spy-qqq]] and [[sector-rotation]], for direct
comparability, not re-derived. No `top_n` parameter (this basket only
ever holds 0 or 1 position, unlike sector-rotation's top-3-of-10).
Monthly rebalance (first trading day of each calendar month) — same
cadence as sector-rotation.

**Killed if:** walk-forward Sharpe (2016-2024, 12 folds, 5 bps fees + 5
bps slippage) fails to clear the standing gate (Sharpe ≥1.0, Sortino
≥1.2). **Also checked:** does the strategy actually use its cash floor
(spend real time flat), or does it just end up perpetually holding SPY —
in which case the absolute-momentum term is decorative and this reduces
to a concentrated equity bet with extra steps.

## Mechanism

See [[dual-momentum]]. The causal story is flight-to-quality capital
reallocation across asset classes during equity stress — institutional
and retail deleveraging out of equities into bonds and/or gold when
trailing equity returns turn negative — distinct from both
[[time-series-momentum]]'s single-asset trend-following story and
[[cross-sectional-momentum]]'s intra-asset-class relative-strength story
(sector rotation). The absolute floor is the specific mechanism that lets
the strategy express "risk-off across the board," not just "which sector
fell least."

## Falsification test

Record which of {SPY, TLT, GLD, CASH} is held at each of the ~108 monthly
rebalances. If CASH's frequency is near zero, the absolute floor never
actually binds and this is really just sector-rotation's construction
with two extra tickers bolted on. If CASH's frequency is very high (say,
>60%), the floor is so restrictive the strategy is closer to an
always-flat baseline than a genuine rotation strategy.

## Manifest

```strategy_manifest
{
  "schema_version": "1.0.0",
  "id": "dual-momentum-equity-bond-gold",
  "wiki_page": "brain/wiki/strategies/dual-momentum-equity-bond-gold.md",
  "market": "us_equities",
  "family": "swing",
  "universe": ["SPY", "TLT", "GLD"],
  "hypothesis": "Ranking SPY/TLT/GLD against each other's trailing 12-1 momentum each month and holding the relative leader -- but only if that leader's own trailing momentum is positive, else cash -- captures a flight-to-quality edge distinct from sector-rotation's always-own-something relative-strength construction. Killed if walk-forward Sharpe does not clear 1.0, or if the strategy never actually uses its cash floor (i.e. always just holds SPY).",
  "signal_spec": { "language": "python", "entrypoint": "strategies/dual_momentum_equity_bond_gold.py:Signal" },
  "risk": { "max_position_pct": 5.0, "stop_loss_pct": 2.0, "stop_loss_cooldown_sessions": 10 },
  "lifecycle": "retired",
  "scorecard": {
    "sharpe_wf": 0.101427, "sortino_wf": 0.239986, "max_drawdown_bt": 1.401386,
    "sharpe_paper": null, "max_drawdown_paper": null, "pnl_live": null,
    "rank": null
  }
}
```

## Evidence

Real walk-forward backtest (2016-01-01 to 2024-12-31, `folds=12`, real
16-symbol Alpaca data restricted to SPY/TLT/GLD,
`data/results/dual-momentum-equity-bond-gold/`): Sharpe 0.101427, Sortino
0.239986, max drawdown 1.401386% (among the lowest recorded in this
vault, behind only ms-shift-spy-vol-regime's 0.786% and
ms-shift-spy-high-displacement's 1.180%), turnover 0.3632 (also among the
lowest recorded, behind only ms-shift-spy-high-displacement's 0.185723 —
holding cash 21% of the time and only ever one position at once keeps
trading light). A clear miss. Fold Sharpes swing widely with no
discernible pattern: `[0.0, -0.126, 0.747, -0.806, 1.236, -1.4, -0.236,
1.78, -1.657, 1.506, -0.821, 0.994]` — six of twelve folds negative. OOS
holdout (trailing 25%, split 2022-09-29): in-sample Sharpe -0.114044
(negative — no positive in-sample edge to hold against the OOS split),
OOS Sharpe 0.715457 — REJECTED on that basis, though the improvement
itself is the same pattern nearly every strategy in this vault shows on
this particular split (2022-Q4-onward conditions broadly favored
long-biased strategies generally).

Falsification check (raw signal,
`scripts/dual_momentum_equity_bond_gold_backtest.py`): 108 monthly
rebalances, holding SPY 49.1% of the time, GLD 24.1%, CASH 21.3%, and TLT
5.6%. The absolute floor genuinely binds — this is not sector-rotation's
construction with extra tickers bolted on, the strategy spends real time
flat — and it's not a single-asset bet either, since GLD and TLT together
account for nearly 30% of selections. The mechanism worked exactly as
designed (a real, verified flight-to-quality rotation across three asset
classes, including real cash time), but the risk-adjusted return was
still weak: structurally worse than both of the concepts it composes —
[[tsmom-spy-qqq]] (0.813) and even [[sector-rotation]] (0.255) — meaning
the extra selectivity from combining an absolute floor with cross-asset
ranking cost more in missed upside (GLD/TLT often lag SPY even when SPY's
own momentum is mediocre) than it saved in avoided drawdowns (the
drawdown improvement is real, just not large enough to compensate on a
Sharpe/Sortino basis, especially with only three assets to rotate among
rather than a genuinely diversified multi-asset sleeve).

## Lifecycle history

- 2026-07-21 — created at `research` — second cross-sectional strategy in
  this vault and the first to compose [[cross-sectional-momentum]] with
  [[time-series-momentum]]'s absolute floor; lookback/skip carried over
  unchanged from tsmom-spy-qqq/sector-rotation for direct comparability,
  no additional parameters to fit. Includes
  `stop_loss_cooldown_sessions: 10` (Option C) from the start per
  [[stop-loss-rearm-coupling]].
- 2026-07-21 — retired — Sharpe 0.101427 / Sortino 0.239986, a clear
  miss, worse than both concepts it composes ([[tsmom-spy-qqq]]'s 0.813
  and [[sector-rotation]]'s 0.255). The falsification test passed
  cleanly in the interesting direction — the absolute floor genuinely
  binds (21.3% cash) and the basket genuinely diversifies across asset
  classes (SPY 49.1%, GLD 24.1%, TLT 5.6%) rather than degenerating into
  either "always SPY" or "always flat" — so the mechanism is real, just
  not profitable enough on this exact three-asset basket over this
  window: drawdown did improve (1.401% vs. tsmom-spy-qqq's 2.305% and
  sector-rotation's 3.130%) but not by enough to offset the opportunity
  cost of rotating out of equities into GLD/TLT during months when SPY's
  own momentum was mediocre-but-still-better. Not a parameter-tuning
  target (lookback/skip fixed for comparability, not searched); if this
  axis gets revisited, the flagged next step is a larger, more
  diversified multi-asset-class sleeve (more than one bond/commodity
  proxy per regime) rather than re-tuning this specific three-asset cut,
  echoing [[sector-rotation]]'s own flagged next step for its axis.
