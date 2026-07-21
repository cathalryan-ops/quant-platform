---
type: concept
created: 2026-07-21
---

# 52-Week High Effect

Proximity to an asset's own trailing 52-week high predicts near-term
continuation (George & Hwang 2004) — and, per their study, is a *better*
predictor of subsequent drift than trailing return itself, subsuming
ordinary momentum rather than just correlating with it. Mechanism is
anchoring bias, not information diffusion: investors use the 52-week high
as a reference point and are reluctant to bid a price above it even when
fundamentals justify it, so news gets underreacted to near the high; once
price breaks through or holds near that anchor, the backlog of
underreaction resolves as continued drift.

## What matters for us

Structurally distinct from [[time-series-momentum]] in construction, not
just parameters: TSMOM is a ratio of two returns (a trailing return over
a lookback); this is a ratio of price to a rolling MAX — a completely
different statistic with a different proposed cause (anchoring/reference-
point bias vs. underreaction-to-flow / trend-following-crowd dynamics).
Two signals can be numerically correlated (both tend to fire during
uptrends) while resting on different causal claims — worth testing
independently rather than assuming a null on one implies a null on the
other.

## Evidence & sources

- George, T. and Hwang, C. (2004), "The 52-Week High and Momentum
  Investing", *Journal of Finance* — the anchoring-bias construction this
  vault's [[52wk-high-spy-qqq]] implementation follows (nearness to
  trailing 252-session high).
