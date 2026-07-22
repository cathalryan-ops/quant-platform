---
type: postmortem
created: 2026-07-22
---

# Pinned 16-symbol universe — diversity/breadth investigation

> Not a strategy result. [[research-campaign-2026-07-21]] flagged the
> 16-symbol snapshot (`sandbox/backtest/DATA.md`) as a possible limiting
> factor for [[sector-rotation]] and [[dual-momentum-equity-bond-gold]] —
> both underperformed and both independently guessed the universe was
> "too narrow" for a fair cross-sectional test. This page checks that
> guess against the actual data (correlation structure, sector/asset-class
> composition, liquidity) instead of leaving it as an inference. No
> strategy was run or re-run for this — that's a separate decision for
> later. Data: `data/us_equities/daily/DIA_GLD_IWM_QQQ_SPY_TLT_XLB_XLE_
> XLF_XLI_XLK_XLP_XLRE_XLU_XLV_XLY_2016-01-01_2024-12-31.parquet`, all 16
> symbols, 2016-01-04 to 2024-12-30, 2263 aligned sessions, daily close-to-
> close returns.

Quantify, don't narrate.

## Composition: what the 16 symbols actually are

- **4 broad US equity index ETFs:** SPY, QQQ, IWM, DIA — different
  market-cap/style slices of the *same* underlying US equity market
  (large-cap blend, large-cap growth-tilted, small-cap, large-cap
  price-weighted).
- **10 SPDR sector ETFs:** XLK, XLF, XLE, XLV, XLI, XLY, XLP, XLU, XLB,
  XLRE — all sub-baskets of the S&P 500, i.e. constituents of SPY itself,
  not an independent asset class.
- **2 non-equity diversifiers:** TLT (20+yr Treasuries), GLD (gold).

So 14 of 16 symbols (87.5%) are all claims on the same underlying asset
class (US equities) sliced by cap tier or sector, not 16 independent
bets. Only 2 symbols sit outside US equities entirely.

## Correlation structure

Full 16-symbol pairwise correlation of daily returns, 2016-2024:

| Subset | Avg pairwise corr | Min | Max |
|---|---|---|---|
| All 16 | 0.513 | -0.31 (TLT/XLF) | 0.973 (QQQ/XLK) |
| 14 equity-only (4 index + 10 sector) | **0.685** | 0.341 (XLE/XLU) | 0.973 (QQQ/XLK) |
| 4 broad index ETFs only (SPY/QQQ/IWM/DIA) | **0.856** | 0.76 (IWM/QQQ) | 0.97 (SPY/DIA, approx) |
| 10 sector ETFs only | 0.625 | 0.341 (XLE/XLU) | 0.88 |

The two "diversifiers" earn the label: TLT correlates at **-0.188** with
the equal-weight equity-block average return, GLD at **+0.084** — both
genuinely low, TLT usefully negative. Everything else in the basket is
solidly positive and mostly north of 0.6.

## PCA: how many independent bets does the 14-symbol equity block give you

Eigen-decomposition of the 14-symbol (4 index + 10 sector) equity
correlation matrix:

| Component | Variance explained | Cumulative |
|---|---|---|
| PC1 | **71.7%** | 71.7% |
| PC2 | 7.9% | 79.6% |
| PC3 | 6.7% | 86.3% |
| PC4–14 | ≤3.1% each | 100% |

A single common factor ("the US equity market went up or down that day")
explains nearly three-quarters of the day-to-day variance across all 14
equity symbols. The next two components combined add another ~15%. The
long tail (PC4–14, 11 components) splits the remaining ~11% — this is
where genuine sector-specific dispersion lives, and it's thin.

## Cross-sectional dispersion vs. market factor (the sector-rotation-relevant number)

For a cross-sectional strategy to have something to rotate into, day-to-
day dispersion *across* the 10 sectors needs to be a meaningful fraction
of the day's overall market move, not swamped by it:

- Daily cross-sectional std across the 10 sector returns: mean 0.757%,
  median 0.668%.
- Daily std of the equal-weight sector-average ("market factor") return:
  1.078%.
- **Ratio: 0.702** — cross-sectional dispersion is about 70% the size of
  the common factor's own daily move.

Not negligible — there is real dispersion to trade — but it's the same
picture as the PCA: roughly 70% of what moves a sector on a given day is
shared with every other sector, leaving the cross-sectional (relative)
signal to work with the remaining minority share.

## Liquidity

Average daily dollar volume across the 16, computed as `close × volume`:

| Symbol | Avg $ volume/day |
|---|---|
| SPY | $28.4B |
| QQQ | $11.6B |
| IWM | $4.8B |
| TLT | $2.1B |
| XLF | $1.7B |
| XLE | $1.4B |
| GLD | $1.4B |
| DIA | $1.2B |
| XLK | $1.1B |
| XLV | $1.0B |
| XLI | $1.0B |
| XLU | $0.9B |
| XLP | $0.8B |
| XLY | $0.7B |
| XLB | $0.4B |
| XLRE | **$0.2B** |

160x spread from top to bottom, but every symbol clears $170M/day —
all 16 are liquid, large, well-arbed ETFs. Liquidity is not a plausible
constraint on any strategy tested against this universe so far;
correlation structure is.

## Verdict

The "too narrow" flag from [[sector-rotation]] and
[[dual-momentum-equity-bond-gold]] is **directionally correct but was
under-specified** — it's not that the universe lacks labeled variety (10
distinct GICS-style sector tickers, 4 index tiers, 2 non-equity assets is
real nominal breadth), it's that the *labeled* variety collapses toward a
single common factor once measured: 71.7% of variance across the 14
equity symbols is one factor, average pairwise correlation among them is
0.685, and the 4 broad index ETFs alone average 0.856 — they are near-
duplicates of each other for cross-sectional purposes. True asset-class
diversification in this snapshot comes down to exactly 2 of 16 symbols
(TLT, GLD), which is consistent with why
[[dual-momentum-equity-bond-gold]]'s 3-asset rotation (SPY/TLT/GLD) had
so little to work with, and why [[sector-rotation]]'s 10-sector rotation
mostly rediscovered XLK's dominance (a single sector riding the same
dominant factor harder, not a genuinely independent cross-sectional
signal) rather than validating broad-based rotation.

This is a data-composition finding, not a mechanism verdict — it does
not by itself say cross-sectional momentum can't work on this data, only
that the effective number of independent bets in the pinned 16-symbol
snapshot is much smaller than 16 (PCA says closer to 3 components carry
meaningful, non-redundant signal, and only 2 symbols are outside US
equities entirely). Whether that's sufficient breadth, and whether a
wider universe would be worth the research budget, is a call for the
human, not this page — no new strategy or wider-universe backtest was
run to answer that question, by design.

## Links

- Strategies flagging the original concern: [[sector-rotation]],
  [[dual-momentum-equity-bond-gold]]
- Concepts: [[cross-sectional-momentum]], [[dual-momentum]]
- Prior synthesis: [[research-campaign-2026-07-21]]
- Data: `sandbox/backtest/DATA.md`,
  `data/us_equities/daily/DIA_GLD_IWM_QQQ_SPY_TLT_XLB_XLE_XLF_XLI_XLK_XLP_XLRE_XLU_XLV_XLY_2016-01-01_2024-12-31.parquet`
  (content hash `sha256:499059d460fe88bdf438ba4746151a42ba57c96fbf068ca24190174a41419bb6`)
