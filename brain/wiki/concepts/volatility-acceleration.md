---
type: concept
created: 2026-07-21
---

# Volatility Acceleration

The ratio of short-window realized volatility to a longer-window baseline
realized volatility, both trailing and causal. A ratio near 1.0 means
current volatility is in line with its recent local regime; a ratio well
above 1.0 means volatility is *expanding fast* — the market is getting
more turbulent right now, independent of whether the underlying trend is
still up, down, or undefined.

## What matters for us

Distinct from [[ms-shift-spy-vol-regime]]'s gate, which filtered on an
*absolute* trailing realized-vol band ([12%, 35%] annualized) — a level
check, static relative to the whole sample. This is a *relative*,
self-referential check (short-window vol vs. the same symbol's own
longer-window vol) that reacts to a regime change starting, not to
whether the current level happens to sit in some fixed range. The
motivating gap: [[time-series-momentum]] is blind to a shock that occurs
inside its own (multi-month) lookback window — [[tsmom-spy-qqq]] was
fully invested through the entire 2020 COVID crash because nothing in a
12-month trailing return can react within days. A fast-reacting vol-ratio
gate is a structurally different, much shorter-horizon signal layered on
top, aimed squarely at that blind spot.

## Evidence & sources

- Motivating gap identified directly in this vault —
  [[tsmom-spy-qqq]]'s Lifecycle history (2026-07-21 retirement).
