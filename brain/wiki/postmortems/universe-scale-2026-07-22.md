---
type: postmortem
created: 2026-07-22
---

# Universe scale vs. cross-sectional momentum — does size help?

> Closes the "genuinely larger, more diversified cross-sectional universe
> (dozens to hundreds of names)" lever [[sector-rotation]] and
> `dual-momentum-equity-bond-gold` both flagged as their next step, and
> which both 2026-07-22 Telegram digests posed as the open question for
> this research line. [[cross-sectional-momentum-stocks50]] tested it
> directly: identical mechanism ([[sector-rotation]]'s `Signal`,
> completely unmodified except `top_n` rescaled to preserve the same ~30%
> concentration ratio), same lookback/skip, same walk-forward protocol,
> the only variable changed is universe composition — 10 correlated
> sector-ETF aggregates vs. 50 individual stocks across the same 11 GICS
> sectors.

## Result

Sharpe 0.280239, Sortino 0.425607 — a clear miss on the 1.0/1.2 gate, and
**not meaningfully different in magnitude** from sector-rotation's own
0.255273/0.390583 on 10 sector ETFs. Scaling the universe by 5x (10 → 50
names) did not move the needle on risk-adjusted return.

## The falsification test resoundingly passed — and that's the point

Sector-rotation's own falsification check (does the selection rotate, or
collapse onto a persistent handful) passed but with a caveat: XLK was
selected in 69.1% of rebalances, meaning much of its result was "found
tech's 2016-2024 dominance," not broad-based rotation. This universe
removes that caveat entirely: **all 50 of 50 names were selected at
least once**, across **93 distinct 15-stock combinations in 94
rebalances** (a near-total reshuffle almost every month) — no analog to
XLK's dominance exists here; MSFT, the most frequently selected single
name, appears in only 73.4% of rebalances (close to XLK's 69.1%, notably
similar despite 5x more names to choose from) and the frequency curve
tails off smoothly rather than concentrating.

So the mechanism genuinely IS finding broad-based rotation across real
single-name dispersion — the universe-diversity postmortem's diagnosis
(sector ETFs wash out idiosyncratic dispersion before ranking) was
correct, and this universe fixes exactly that. **The fix didn't help the
Sharpe.** More real dispersion in the ranking pool does not, by itself,
turn a weak cross-sectional-momentum result into a strong one.

## What got worse: turnover

Turnover is 7.858997 — roughly **5x** sector-rotation's 1.524093, itself
already the second-highest turnover recorded in this vault. Individual
stock rankings churn far more month-to-month than sector-level
aggregates (which smooth idiosyncratic single-name noise across ~50
underlying constituents each). The near-total monthly reshuffle that
resolved the concentration critique above is the same property that
drives this cost up. Max drawdown is also worse: 8.316661% vs
sector-rotation's 3.1296% (both still under the 15% gate independently,
but a real degradation, not noise).

## The OOS pattern inverts here — the first time in this vault

Every walk-forward strategy in this vault to date that reported an OOS
holdout showed OOS Sharpe *improve* on in-sample on the standard trailing-
25%/2022-09-29 split — attributed (see [[sector-rotation]]'s own Evidence
section) to 2022-Q4-onward conditions broadly favoring long-biased
strategies generally, not to anything mechanism-specific. This strategy
is the first to break that pattern: in-sample Sharpe 0.53059, OOS Sharpe
0.295872, a **-44.2% degradation**, explicitly REJECTED by the
`oos_reject_threshold=0.35` gate (not just failing the raw walk-forward
number). Two readings, not resolved here: (a) the vault-wide OOS-improves
pattern was never really universal, just correlated with strategies that
happened to be long-biased through a favorable stretch, and this
high-turnover, frequently-reshuffling strategy is different enough in
kind to break it; or (b) genuine overfitting to in-sample idiosyncratic-
stock noise that doesn't generalize — plausible given how much more the
selection churns here than in any prior cross-sectional test. Flagged for
awareness, not chased further (not a parameter-tuning target per the
strategy's own manifest).

## Conclusion — this closes the universe-scale lever

Falsifies the standing hypothesis (raised independently by both
sector-rotation and dual-momentum-equity-bond-gold, and posed as an open
question in both 2026-07-22 digests) that universe *size* was the
limiting factor for cross-sectional momentum on this data. A 5x larger,
genuinely-more-diverse-in-composition universe reproduced almost the
identical Sharpe, at meaningfully higher turnover and drawdown, and with
a worse (not better) OOS-generalization signature. The mechanism itself
— rank-by-trailing-12-1-momentum, rotate into the top ~30% — appears to
be the limiting factor, not the universe it's been tested on. Per the
open question both recent digests posed (bigger universe vs. pausing
backtest-only research on the current fixed windows), this result argues
against spending further data-pinning effort scaling the universe up
again for the same mechanism; a different mechanism class, or a pause, are
the remaining live options.
