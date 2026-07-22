---
type: strategy
created: 2026-07-22
---

# Market-Structure-Shift + Displacement — BTC/USD, ETH/USD

Direct follow-up to [[tsmom-btc-eth]]'s retirement, per
[[blend-leg-search-2026-07-22]]'s closing recommendation: crypto momentum
deserves its own comparison, not a graft onto the equity blend chain.
tsmom-btc-eth tested one mechanism on crypto (absolute momentum, Sharpe
0.219, clear miss). This tests the *second* mechanism from the equity
blend's own recipe — [[market-structure-shift]] +
[[displacement]] — on the same crypto universe, both to check the
mechanism transfers and, if it does, to test whether the two crypto legs
are independent enough to blend the same way [[tsmom-ms-shift-blend]] did
on equities.

## Hypothesis

[[market-structure-shift]]/[[displacement]], completely unmodified
(`strategies/ms_shift_spy_high_displacement.py:Signal`, same
`swing_lookback=3`, `atr_period=14`, `displacement_mult=2.0`), applied to
BTC/USD and ETH/USD. Unlike [[tsmom-btc-eth]], **no calendar-unit
conversion is needed or applied**: `swing_lookback`, `atr_period`, and
`displacement_mult` are pure bar-count/price-range parameters with no
"months" or trading-day-per-year semantics baked in (confirmed by reading
the signal's own implementation — no reference to session counts per
year anywhere in `_atr_at`/`_is_swing_high`/`_is_swing_low`), so the
identical class is reused directly on crypto's calendar-day bars with
zero wrapper code, a stronger form of "unmodified" than tsmom-btc-eth's
own thin wrapper needed.

If the ceiling found on equities (day-scale structure breaks and
month-scale absolute momentum both land near Sharpe 0.8, independently)
is a property of these specific mechanisms rather than the US-equity
universe, this should show a comparable pattern on crypto to
tsmom-btc-eth's own result — some real signal, likely still short of the
gate given crypto's smaller/choppier sample. The more interesting
question this page adds: does `ms_shift`'s displacement-triggered entry
actually catch the November 2022 FTX-collapse shock (the sharp,
within-day-scale move it's specifically designed to react to), in
contrast to tsmom-btc-eth's mechanically-blind trailing-return
construction? If so, the two crypto legs may have a genuinely different
shock-response profile — the same structural precondition
([[signal-blending]]'s premise) that made the equity blend work.

**Killed if:** walk-forward Sharpe (2021-01-01 to 2024-12-31, `folds=8`,
same as tsmom-btc-eth for matched statistical power) fails to clear the
standing 1.0/1.2 gate — no special exception. **Also checked:** does the
raw signal actually react to the FTX-collapse week (displacement
threshold crossed, trend flips), in contrast to tsmom-btc-eth's confirmed
100%-flat non-reaction — and if both this strategy and tsmom-btc-eth
individually miss the gate, is their correlation low enough that a
crypto-native blend is still worth testing (the same question dual-
momentum/tsmom-tlt-gld answered differently on equities).

## Mechanism

See [[market-structure-shift]] and [[displacement]]. No new causal claim
— confirmed swing-structure breaks accompanied by an outsized true range
predict continuation, the same premise validated on SPY/QQQ. Applied to
crypto, the counterparty story shifts from institutional
underreaction/rebalancing flows (the equity story) to retail-heavy
momentum chasing and liquidation-cascade dynamics common in crypto
markets — a break confirmed by a genuine volatility expansion is more
likely a real regime change than one of the many low-conviction swing
points that don't hold, in a market known for frequent liquidation-driven
whipsaws.

## Falsification test

Same two-part structure as tsmom-btc-eth's: (1) report flat-fraction
during the slow 2021-11-10 to 2022-11-21 bear decline and the acute
2022-11-06 to 2022-11-14 FTX-collapse week separately, not just aggregate
Sharpe; (2) report the raw signal's correlation and agreement rate with
tsmom-btc-eth's raw signal (same construction as
[[tsmom-ms-shift-dualmom-blend]]/[[tsmom-ms-shift-tltgld-blend]]'s own
falsification checks) to determine whether a crypto-native blend is worth
testing at all before building one.

## Manifest

```strategy_manifest
{
  "schema_version": "1.0.0",
  "id": "ms-shift-btc-eth",
  "wiki_page": "brain/wiki/strategies/ms-shift-btc-eth.md",
  "market": "crypto",
  "family": "ms_shift",
  "universe": ["BTC/USD", "ETH/USD"],
  "hypothesis": "Market-structure-shift + displacement (swing_lookback=3, atr_period=14, displacement_mult=2.0, unmodified from ms-shift-spy-high-displacement, no calendar conversion needed) applied to BTC/USD and ETH/USD. Tests whether the day-scale structure-break mechanism transfers to crypto the way absolute momentum was already tested via tsmom-btc-eth, and whether the two mechanisms' crypto-native correlation is low enough to make a crypto blend worth attempting. Killed if walk-forward Sharpe does not clear the standing 1.0/1.2 gate.",
  "signal_spec": { "language": "python", "entrypoint": "strategies/ms_shift_spy_high_displacement.py:Signal" },
  "risk": { "max_position_pct": 5.0, "stop_loss_pct": 2.0, "stop_loss_cooldown_sessions": 10 },
  "lifecycle": "retired",
  "scorecard": {
    "sharpe_wf": 0.559667, "sortino_wf": 0.907426, "max_drawdown_bt": 2.741119,
    "sharpe_paper": null, "max_drawdown_paper": null, "pnl_live": null,
    "rank": null
  }
}
```

## Evidence

Real walk-forward backtest (2021-01-01 to 2024-12-31, `folds=8`, real
BTC/USD+ETH/USD Alpaca crypto data, `data/results/ms-shift-btc-eth/`,
`scripts/ms_shift_btc_eth_backtest.py`): **Sharpe 0.559667, Sortino
0.907426, max drawdown 2.741119%, turnover 1.640095.** A clear miss on
the 1.0/1.2 gate but a materially closer one than [[tsmom-btc-eth]]'s
0.21921 — 44% short of the Sharpe bar vs. tsmom-btc-eth's 78% short.
Fold Sharpes: `[-0.508, 0.747, -0.502, -0.251, 0.892, 1.833, 0.941,
1.325]` — half the folds negative, but no fully-flat (zero-variance)
folds the way tsmom-btc-eth had three. Turnover (1.640) is more than
double tsmom-btc-eth's (0.768) — this mechanism trades far more often on
crypto, consistent with its equity behavior (ms_shift always had higher
turnover sensitivity than tsmom). OOS holdout (trailing 25%, split
2024-01-02): in-sample Sharpe 0.3485, OOS Sharpe 1.117489 — improves
substantially on in-sample (PASSED), though the same 2024-bull-year
holdout caveat from tsmom-btc-eth's own page applies (a short, one-year,
single-regime OOS window on a 4-year sample).

**Falsification check 1 (flat-fraction during known drawdowns) —
partial, not full, confirmation of the shock-reaction hypothesis:**
during the acute FTX-collapse week, ms-shift-btc-eth was flat 77.8% of
sessions on both symbols — in the market 22.2% of the time, a real but
modest reaction, in contrast to tsmom-btc-eth's confirmed 100%-flat
non-reaction to the same week. During the slow 2022 bear decline, the
asymmetry is more interesting: ms-shift-btc-eth was flat only 53.8% on
BTC/USD (more exposed than tsmom-btc-eth's 90.2% flat) but flat 85.7% on
ETH/USD (comparable to tsmom-btc-eth's 68.4% flat, actually more
defensive). The two mechanisms are not just differently-timed versions
of the same story — they have genuinely different, asymmetric exposure
profiles per symbol during the same drawdown.

**Falsification check 2 (correlation and signal agreement vs
tsmom-btc-eth) is the strongest finding on this page**: Pearson
correlation between the two legs' daily returns is **0.4319** — moderate,
comparable to or below the equity blend's own tsmom/ms-shift correlation
(0.5522) — and raw signal agreement is only **50.4% (BTC/USD)** and
**45.9% (ETH/USD)**, close to coin-flip, meaning the two signals are
long/flat on genuinely different days more often than not. This is a
stronger diversification signature than the equity blend's own legs
showed at inception, and immediately raises the same question
[[tsmom-ms-shift-blend]] answered on equities: does blending these two
crypto-native legs beat both individually? See
[[ms-shift-tsmom-blend-btc-eth]] for the result.

## Lifecycle history

- 2026-07-22 — created at `research` — direct follow-up to
  [[tsmom-btc-eth]]'s retirement and
  [[blend-leg-search-2026-07-22]]'s recommendation to test crypto
  momentum as its own comparison. Reuses
  `ms_shift_spy_high_displacement.py:Signal` completely unmodified (no
  wrapper needed, confirmed no calendar-dependent parameters), same
  crypto snapshot and `folds=8` as tsmom-btc-eth for a directly
  comparable methodology.
- 2026-07-22 — retired — Sharpe 0.559667, a clear miss on the standing
  gate but the strongest single-leg crypto result so far (44% short vs.
  tsmom-btc-eth's 78% short). The falsification checks are the real
  finding: a real, if partial, reaction to the FTX shock (22.2% in-market
  vs tsmom-btc-eth's 0%) and — most importantly — moderate correlation
  (0.4319) and near-coin-flip raw signal agreement (45.9-50.4%) against
  tsmom-btc-eth, a stronger independence signature than the equity
  blend's own legs had at inception (0.5522). Immediately tested as a
  blend leg — see [[ms-shift-tsmom-blend-btc-eth]].