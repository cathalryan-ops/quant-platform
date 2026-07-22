---
type: postmortem
created: 2026-07-22
---

# Blend third-leg search — 2026-07-22

> Cross-strategy synthesis, not a single paper/live review — closes out the
> blend-leg-search line of research started by
> [[research-campaign-2026-07-21]]'s proposed next lever. Three blend
> variants were tested in sequence today; this page records the pattern
> across them and the decision to stop searching rather than push for a
> fourth leg.

Quantify, don't narrate.

## Every blend variant, ranked

All real walk-forward backtests, 2016-01-01 to 2024-12-31, 12 folds, 5 bps
fees + 5 bps slippage, against the standing gate (`sharpe_wf` ≥1.0,
`sortino_wf` ≥1.2). **All still fail `passed_thresholds`.**

| Strategy | 3rd leg | Sharpe | Sortino | Max DD % | vs. 2-leg baseline |
|---|---|---|---|---|---|
| [[tsmom-ms-shift-blend]] | (2-leg baseline) | 0.884 | 1.297 | 1.234 | — |
| [[tsmom-ms-shift-dualmom-blend]] | dual-momentum-equity-bond-gold | 0.863 | 1.305 | 1.139 | -0.021 (regression) |
| [[tsmom-ms-shift-tltgld-blend]] | tsmom-tlt-gld | **0.990** | **1.507** | 1.090 | **+0.105** |

**tsmom-ms-shift-tltgld-blend is the best result in this vault to date**,
missing the 1.0 Sharpe gate by 0.010368 (1.0%) — the closest any strategy
here has ever come, more than 10x closer than the 2-leg blend's own
11.6%-short near-miss.

## The pattern: correlation regime beat standalone strength

The two third-leg candidates were chosen for opposite reasons and produced
opposite outcomes:

- **dual-momentum-equity-bond-gold** — standalone Sharpe 0.101, weaker
  than tsmom-tlt-gld's own 0.173, but picked first because its own
  falsification test proved a *real* mechanism (genuine cash floor,
  genuine cross-asset rotation), on the working assumption that
  "real mechanism" was the bar to clear. It measured **0.5852 correlation
  to tsmom-spy-qqq** — higher than tsmom and ms-shift's own correlation to
  each other (0.5522) — because its cross-sectional ranking reuses tsmom's
  identical lookback=252/skip=21 logic on SPY as one of its three
  candidates. Blending it in made the 3-way Sharpe *worse* than the 2-leg
  baseline, despite the stronger-mechanism screening.
- **tsmom-tlt-gld** — built specifically to break that confound: same
  absolute-momentum mechanism, applied to TLT/GLD, sharing zero symbols
  with either existing leg. Standalone Sharpe (0.173) is weaker than
  dual-momentum would suggest is needed, but correlation to both existing
  legs is **near-zero** (0.0051 vs tsmom, 0.0689 vs ms-shift). Blending it
  in lifted the 3-way Sharpe well above the 2-leg baseline.

**The lesson for future leg selection:** when picking a candidate to add
to an existing blend, correlation to the *existing legs specifically*
matters more than the candidate's own standalone Sharpe. A leg with a
real but weak edge and near-zero correlation can lift a blend further than
a leg with a stronger edge and moderate correlation. This directly
supersedes the [[tsmom-ms-shift-dualmom-blend]] screening note's implicit
assumption (a real, non-null mechanism was the main bar to clear) — real-
and-uncorrelated is a stronger requirement than just real.

## Why the search stops here, not at a fourth leg

Considered and declined (human + agent discussion, 2026-07-22): a fourth
leg was tempting given how close 0.989632 is to the gate, but three
reasons argued against continuing on this same axis:

1. **No remaining low-correlation candidate in the pinned universe.** TLT
   and GLD — the only genuinely non-equity-correlated assets pinned (per
   [[pinned-universe-diversity-2026-07-22]]) — are now both spent on leg
   3. Every other pinned symbol (10 sector ETFs, IWM, DIA) shares the same
   71.7%-of-variance PC1 equity factor documented in that postmortem, and
   would likely repeat dual-momentum's correlated-not-diversifying
   outcome, not tsmom-tlt-gld's.
2. **Crypto can't cleanly extend this specific blend.** [[tsmom-btc-eth]]
   is the only other genuinely uncorrelated asset class already tested in
   this vault, but its pinned data starts 2021-01-01 vs. this blend's
   2016-2024 window — joining it would truncate the backtest period and
   invalidate every comparison made across all three blend variants above,
   not a like-for-like fourth leg.
3. **Process-discipline risk.** Two third-leg candidates have now been
   tried in immediate succession, keeping the one that worked, against the
   same fixed 2016-2024 sample and the same 2022-09-29 OOS split used by
   every other strategy in this vault. `oos.py`'s own docstring flags this
   exact risk: repeated re-runs against one OOS window implicitly tune
   against it even without an explicit parameter sweep. A fourth attempt
   on the same axis — search until something crosses 1.0 — would cross
   from principled leg selection into exactly that pattern.

**Decision: stop here.** [[tsmom-ms-shift-tltgld-blend]] (Sharpe
0.989632) stands as the headline result of this research line. If
diversification is revisited, the next honest step is testing crypto
momentum as its own separate comparison (judged on its own 2021-2024
window, not grafted onto this blend chain), not a mechanical fourth-leg
search on the same fixed sample.

## Verdict & follow-ups

No new gate-review flag filed — the standing 1.0/1.2 gate discipline
already covered this case explicitly on
[[tsmom-ms-shift-blend]]'s own Lifecycle history (human declined to
loosen it for an 11.6%-short near-miss, on principle; this 1.0%-short
result is materially closer but the same reasoning applies, arguably more
so, since holding the line kept the bar meaningful for exactly this kind
of result). This page exists to close the blend-leg-search axis cleanly
and record the reusable correlation-over-strength finding for whichever
research direction comes next.

**Update, same day — the "crypto as its own comparison" follow-up
refines the headline finding.** [[ms-shift-btc-eth]] and
[[ms-shift-tsmom-blend-btc-eth]] tested the same blending lever on
BTC/USD, ETH/USD (correlation 0.4319, comparable to the equity legs'
0.5522) and got the opposite result: the crypto blend (0.406965) is
*worse* than its stronger leg alone (ms-shift-btc-eth, 0.559667). The
cause is not correlation — it's that the two crypto legs are 2.55x apart
in individual Sharpe (0.559667 vs. tsmom-btc-eth's 0.21921), vs. the
equity legs' 7% gap (0.813 vs. 0.759). Fixed 50/50 weighting between
unequal-strength legs dilutes the stronger leg more than moderate
correlation compensates for. **Revised rule for future leg selection:**
correlation to existing legs is necessary but not sufficient for
equal-weight blending to help — the legs also need comparable individual
strength, or the weight needs to reflect the imbalance (not attempted
here, since fitting a weight to this exact sample repeats the
overfitting pattern this vault avoids elsewhere).

## Links

- Strategies reviewed: [[tsmom-ms-shift-blend]],
  [[tsmom-ms-shift-dualmom-blend]], [[tsmom-tlt-gld]],
  [[tsmom-ms-shift-tltgld-blend]], [[ms-shift-btc-eth]],
  [[ms-shift-tsmom-blend-btc-eth]]
- Related: [[research-campaign-2026-07-21]] (proposed the original 2-leg
  blend), [[pinned-universe-diversity-2026-07-22]] (basis for ruling out
  sector ETFs as 4th-leg candidates), [[tsmom-btc-eth]] (the only other
  uncorrelated asset class tested, ruled out for a date-range mismatch)
- Concepts: [[signal-blending]], [[time-series-momentum]],
  [[dual-momentum]]
- Results: `data/results/tsmom-ms-shift-dualmom-blend/`,
  `data/results/tsmom-tlt-gld/`, `data/results/tsmom-ms-shift-tltgld-blend/`
