---
type: postmortem
created: 2026-07-22
---

# Low-volatility anomaly on 50 stocks — does it hold on this sample?

> First test in this vault of a mechanism outside the four families tried
> so far (momentum — time-series and cross-sectional, market-structure-
> shift, mean-reversion, calendar). [[low-vol-anomaly-stocks50]] ranks the
> same 50-single-name-stock universe as
> [[cross-sectional-momentum-stocks50]] by trailing 1-year realized
> volatility instead of trailing return, holding the 15 LEAST volatile
> names — the opposite ranking direction from every prior cross-sectional
> strategy here.

## Result

Sharpe 0.518773, Sortino 0.782279 — a clear miss on the 1.0/1.2 gate, but
the **best of the three cross-sectional strategies tested in this vault**
(sector-rotation 0.255273, cross-sectional-momentum-stocks50 0.280239,
this one 0.518773). OOS holdout REJECTED (+35.7% degradation, just over
the 35% threshold) — the second strategy in a row here (after
cross-sectional-momentum-stocks50) whose OOS split degrades instead of
improving on in-sample.

## The composition check passed cleanly — it found real defensive names

96 of ~108 monthly rebalances produced a selection; 61 distinct 15-stock
combinations, 37 of 50 names used at least once. Less rotation than the
momentum test's 93 combos, but the persistent core — PEP (100%), KO
(100%), PG (96.9%), JNJ (91.7%), DUK (88.5%), SO (86.5%), MCD (84.4%) —
is exactly the textbook defensive low-vol cluster (staples, utilities,
healthcare) the literature predicts, not a single-name artifact like
sector-rotation's XLK problem. The signal is measuring what it claims to
measure.

## The real finding: the anomaly didn't just fail to appear, it inverted

This is the falsification test that matters here, and it's a clean
reject. Gross, cost-free annualized numbers over the full sample:

| | ann. return | ann. vol | raw Sharpe |
|---|---|---|---|
| low-vol-15 basket | 7.21% | 15.04% | 0.5386 |
| equal-weight all-50 benchmark | 10.53% | 17.48% | 0.6608 |

The low-vol cut reduced volatility by 14.0% relative to the benchmark —
exactly what a vol-ranking signal should do. But it reduced *return* by
31.5%, more than twice as fast. That's not a risk-reduction tautology
(a tautology would show Sharpe roughly unchanged, return falling in step
with vol); it's worse than a tautology — the low-vol basket's own raw
Sharpe sits *below* an unweighted buy-and-hold of the same universe. On
this 50-stock, 2016-2024 sample, avoiding volatility cost more in return
than it saved in risk.

## Why this result is trustworthy, not a bug

Three things rule out an implementation error rather than a genuine
null: (1) the composition is exactly the expected defensive-sector
cluster, not noise; (2) the vol-reduction direction is correct (14%
lower, as intended) — only the return side inverted; (3) unit tests
confirm the signal correctly ranks by ascending (not descending)
volatility and holds the calmest names, so the ranking direction itself
isn't the bug. The likely economic reading: 2016-2024 was a strong,
persistently long-biased period for US equities (reflected across nearly
every strategy in this vault's walk-forward numbers), and defensive/
low-vol sectors structurally lag broad market upside in exactly that
kind of stretch — the well-documented flip side of the low-vol anomaly's
usual crash-protection value, which this single-period sample without a
major bear stretch doesn't get to show.

## What this means for the "new mechanism class" lever

This closes out the low-volatility anomaly specifically as a candidate
on this universe/period — it is not a promotion candidate and not a
parameter-tuning target (lookback/top_n were fixed a priori for
comparability, not searched; a long-short Betting-Against-Beta variant is
flagged as a genuinely different, untested risk profile, not implied by
this result). It does **not** close the broader "different mechanism
class" lever itself — this is one mechanism among several untried ones
(e.g. pairs/stat-arb relative-value, overnight-vs-intraday decomposition)
and a single null here says the anomaly doesn't hold on this sample, not
that no non-momentum mechanism can. Worth flagging for awareness: this is
now the fourth structurally distinct mechanism (after time-series
momentum, market-structure-shift, and cross-sectional momentum) to land
in the same Sharpe ~0.25-0.9 band on this vault's pinned equity data —
another data point for the standing question of whether that ceiling is
a property of the 2016-2024 US-equity sample itself rather than of any
one signal design.
