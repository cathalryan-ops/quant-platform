<!-- processed: 2026-07-20 -->
# ms-shift-spy-v1 — fold-level regime hypothesis (2016-2024 walk-forward)

Notes written after the repo owner's real walk-forward backtest of
`ms-shift-spy-v1` (SPY+QQQ, daily bars, 2016-01-01 to 2024-12-31, 5 folds)
came back with overall walk-forward Sharpe 0.674 (below the 1.0 promotion
threshold) but highly uneven per-fold Sharpes:

| fold (chronological) | Sharpe |
|---|---|
| 1 | 0.313 |
| 2 | 0.428 |
| 3 | 1.45 |
| 4 | -0.32 |
| 5 | 1.45 |

The spread (two strong folds, one negative, two mediocre) looks more like
regime-dependence than a uniformly absent edge. This note approximates
where each fold sits on the calendar and cross-references that against
known US equity market regimes, to turn "regime-dependence" from a vague
guess into a testable hypothesis.

## How the fold boundaries were approximated

`sandbox/backtest/backtest/engine.py`'s `_walk_forward()` builds folds with
`np.array_split(returns.to_numpy(), folds)` on the strategy's daily return
series (`returns = pf.returns()` from vectorbt's `Portfolio.from_orders()`),
`folds` defaulting to 5, over the full requested period. This session has no
Alpaca credentials and no snapshot in this repo (`data/` is gitignored, the
real snapshot lives only in the owner's environment), so the *actual*
return-series split can't be reproduced here.

What can be reproduced without any price data: the NYSE trading-day
calendar. Using `pandas_market_calendars`'s NYSE schedule for
2016-01-01..2024-12-31 (2,264 trading days) and splitting that date index
with `numpy.array_split(days, 5)` — the same split primitive the engine
uses, applied to the day index instead of the return array — gives an
approximation of each fold's calendar range:

| fold | approx. start | approx. end | trading days |
|---|---|---|---|
| 1 (index 0) | 2016-01-04 | 2017-10-18 | 453 |
| 2 (index 1) | 2017-10-19 | 2019-08-08 | 453 |
| 3 (index 2) | 2019-08-09 | 2021-05-26 | 453 |
| 4 (index 3) | 2021-05-27 | 2023-03-15 | 453 |
| 5 (index 4) | 2023-03-16 | 2024-12-31 | 452 |

Two sources of imprecision, both worth naming up front:

1. The real fold split is on the *return series*, which starts only after
   `ms_shift`'s warmup period, not on the raw calendar. With default
   manifest params (`swing_lookback=3`, `atr_period=14`), the signal needs
   an ATR window of 14 bars plus a few bars of swing confirmation lag
   before it can fire — roughly 2-3 trading weeks. Against a ~9-year, 2,264
   trading-day span this shifts every boundary by well under 1% of the
   total length, i.e. a few trading days at most. Negligible for
   fold-to-regime mapping at monthly resolution, but it means the dates
   above are not exact.
2. `np.array_split` on 2,264 items into 5 chunks gives four chunks of 453
   and one of 452 (the remainder is distributed to the first chunks) —
   mirrored above. If the real return series has fewer rows than the raw
   calendar (because of the warmup dropped rows, or any missing bars), the
   exact split points shift by a similarly small amount.

Net: treat the boundaries above as accurate to within roughly 1-3 weeks,
not exact dates.

## Cross-referencing folds against known market regimes

- **Fold 1 (~2016-01 to 2017-10), Sharpe 0.313.** Opens in the Jan-Feb 2016
  China/oil growth-scare selloff and its recovery, then transitions into
  the unusually low-volatility 2016-2017 "melt-up" bull market. Mixed:
  one sharp-but-short bearish structure break followed by a long, low-
  amplitude grind that offers a long-only continuation strategy relatively
  little to work with (few large-range displacement bars in a low-vol
  trend). A mediocre-not-negative Sharpe is consistent with that.

- **Fold 2 (~2017-10 to 2019-08), Sharpe 0.428.** Contains the Feb 2018
  "Volmageddon" vol-spike, the Q4 2018 selloff (SPX down ~20% peak-to-
  trough into Dec 2018, one of the sharpest non-recession drawdowns of the
  decade), and the V-shaped 2019 recovery. This is a genuinely choppy,
  whipsaw-prone window — repeated sharp reversals are the classic failure
  mode for a trend/continuation strategy, since displacement-confirmed
  breaks fire in both directions and a long-only implementation eats the
  downside legs as flat time rather than profit, while false breakouts on
  the way back up cost money. A mediocre, not disastrous, Sharpe fits.

- **Fold 3 (~2019-08 to 2021-05), Sharpe 1.45.** Contains the Feb-Mar 2020
  COVID crash — about as clean a "displacement" event as exists in market
  history, huge range bars on a confirmed bearish structure break — followed
  by the fastest, strongest bull recovery on record through 2020-2021. This
  is close to the textbook setup the strategy's hypothesis describes: a
  displacement-confirmed shift followed by strong, sustained multi-day
  continuation. A standout Sharpe here is well explained by the regime.

- **Fold 4 (~2021-05 to 2023-03), Sharpe -0.32.** Covers the back half of
  the 2021 bull run into its Nov 2021 top, then nearly all of the 2022 bear
  market — a sustained decline driven by Fed rate hikes and inflation,
  punctuated by several sharp, high-volatility bear-market rallies (e.g.
  the ~17% SPX rally July-Aug 2022, and the Oct-Nov 2022 rally), and tips
  into the very start of the March 2023 regional-bank stress (SVB) if the
  boundary runs a couple weeks later than estimated. This is the fold that
  best matches the -0.32 result.

- **Fold 5 (~2023-03 to 2024-12), Sharpe 1.45.** Covers the 2023-2024
  AI/mega-cap-led rally — a strong, comparatively low-chop uptrend (with a
  brief but sharp Aug 2024 vol spike from the yen carry-trade unwind that
  likely produced one clean displacement event rather than a chop
  regime). Another good match for the strategy's textbook setup, similar in
  character to fold 3.

## Leading hypothesis for the negative fold

**Fold 4 (~May 2021 - Mar 2023, Sharpe -0.32) most plausibly corresponds to
the 2022 bear market.** The leading hypothesis: `ms-shift-spy-v1` is
long-only and displacement-gated, so in a sustained downtrend it should
mostly sit flat rather than lose money outright when bearish structure
shifts correctly keep it out of the market — a flat/near-zero-return fold
would show up as a near-zero, not negative, Sharpe. A meaningfully
*negative* Sharpe instead suggests the strategy was repeatedly triggered
*long* by displacement-confirmed bullish structure shifts during the
2022 bear-market rallies (the July-Aug 2022 and Oct-Nov 2022 rallies both
had wide-range up bars breaking recent swing highs — exactly what the
`displaced and close[t] > last_swing_high` condition looks for), only for
those rallies to fail and roll back into the downtrend. That is the classic
whipsaw failure mode for a trend-continuation strategy in a "grinds down,
rips up, grinds down again" macro regime, and it's consistent with the
wiki's own falsification framing (`brain/wiki/strategies/ms-shift-spy.md`):
the displacement filter is supposed to separate real institutional breaks
from noise, and 2022's bear-market rallies are exactly the kind of
large-participant-driven-but-ultimately-failed move that filter would not
obviously catch, since they were large and fast, not noisy.

## Confidence and caveats

- **This is a hypothesis, not a confirmed finding.** The fold boundaries
  above are approximated purely from NYSE trading-day counts via
  `numpy.array_split`, replicating the split *mechanism* the engine uses —
  they are not the actual return-series split from the real backtest run,
  which required the fetched Alpaca snapshot that exists only in the
  owner's environment and is not present in this repo (`data/` is
  gitignored).
- Because of that, and because of the small additional offset from the
  signal's ~2-3-week warmup period (see above), **specific date claims in
  this note could be off by up to a few weeks at each fold boundary.** In
  particular, whether fold 4 starts inside the tail of the 2021 bull run
  or slightly earlier/later, and whether it captures the very start of the
  March 2023 SVB stress, is uncertain at the day level.
- The mapping of folds 3 and 5 to "clean trend, displacement works well"
  and fold 4 to "chop/whipsaw, displacement produces false long entries"
  is a plausible narrative built from known macro history, not a measured
  property of the actual signal output. It has not been checked against
  the real per-day P&L, trade log, or entry/exit dates of the strategy.
- The mediocre (not negative) Sharpes in folds 1-2 are consistent with a
  "some chop, some low-vol grind, no big clean displacement events" story,
  but that's also unverified against actual trade-level data.
- Bottom line: treat "the strategy has a real edge that's regime-
  conditional, weak in choppy bear-market/whipsaw regimes and strong in
  clean post-shock recoveries" as the working hypothesis to test next, not
  as an established result.

## Follow-up: 12-fold re-run result (real data, run by the operator)

The follow-up task filed above proposed re-running the same walk-forward
backtest at `folds=12` to test whether weak/negative Sharpes cluster inside
the 2022 rate-hike bear market. The operator ran it against the real,
cached Alpaca snapshot. Result (overall walk-forward Sharpe 0.657, close to
the original 0.674 — the mean signal is stable across fold counts):

| fold | dates | sharpe |
|---|---|---|
| 0 | 2016-01-04 – 2016-09-30 | -0.087 |
| 1 | 2016-10-03 – 2017-07-03 | 0.471 |
| 2 | 2017-07-05 – 2018-04-04 | 0.818 |
| 3 | 2018-04-05 – 2019-01-03 | 0.536 |
| 4 | 2019-01-04 – 2019-10-03 | 0.096 |
| 5 | 2019-10-04 – 2020-07-06 | **2.086** |
| 6 | 2020-07-07 – 2021-04-06 | **1.292** |
| 7 | 2021-04-07 – 2022-01-03 | 0.378 |
| 8 | 2022-01-04 – 2022-10-03 | **0.0** |
| 9 | 2022-10-04 – 2023-07-05 | 0.613 |
| 10 | 2023-07-06 – 2024-04-03 | **1.7** |
| 11 | 2024-04-04 – 2024-12-31 | -0.022 |

**The "2022 whipsaw" hypothesis is falsified by this test, per its own
stated falsification criterion.** Fold 8 covers almost the entire 2022
bear market — including the Jul-Aug rally previously blamed for a whipsaw
entry — and comes back exactly flat (0.0), not negative. Fold 9, covering
the Oct-Nov 2022 rally and the March 2023 SVB stress, comes back positive
(0.613). No fold spanning the original 5-fold "fold 4" window (~2021-05 to
2023-03) is negative at 12-fold resolution. The single -0.32 result at
5-fold resolution does not reproduce when that same stretch is split
finer — the simplest reading is that it was an artifact of where that
particular 5-way split's boundaries fell (a variance/autocorrelation
interaction within that specific window), not a real, reproducible
2022-specific effect.

**Revised working characterization:** three folds stand out clearly above
the rest — 2019-10→2020-07 (2.086, COVID crash + V-recovery), 2020-07→
2021-04 (1.292, continued recovery), and 2023-07→2024-04 (1.7, AI/mega-cap
rally). Every other fold sits in a mediocre 0.0–0.82 band, with the two
weakest (2016 open, -0.087; 2024 close, -0.022) barely negative. This
looks less like "avoids bad regimes, struggles in chop/bear markets" and
more like **a few genuinely strong post-shock continuation windows carry
almost the entire edge, while the rest of the time performance is close to
noise.** That's a real pattern worth naming precisely, but a less
favorable one than the original hypothesis: it doesn't describe a
strategy with a durable, regime-conditional edge so much as one that
occasionally catches a big, clean move and is roughly flat otherwise.

This does not change the retirement decision (both fold counts give an
overall Sharpe well below the 1.0 promotion threshold) — it refines *why*
the edge is weak, which is the more useful takeaway for the next research
iteration than the retirement decision itself.
