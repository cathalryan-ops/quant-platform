---
type: concept
created: 2026-07-21
---

# Time-Series Momentum

An asset's own trailing return predicts its near-term future return: after
a sustained trailing uptrend, near-term drift tends to stay positive
(and vice versa). Unlike cross-sectional momentum (rank assets against
each other, long the winners), this is "absolute" — each asset is judged
only against its own history, so it applies even to a single-asset or
two-asset universe. Distinct in every dimension from the day-scale
mechanisms already in this vault: no swing/displacement geometry
([[market-structure-shift]], [[displacement]]) and no single-session
shock ([[mean-reversion-spy-qqq]]'s premise) — the signal is a multi-month
trailing return, and a position is held for however long that trend stays
intact, not a fixed number of sessions.

## What matters for us

The canonical academic construction (Moskowitz/Ooi/Pedersen 2012, "Time
Series Momentum") uses a trailing 12-month return, skipping the most
recent month before measuring it. The skip exists specifically to net out
the *opposite*-signed, short-term reversal effect — the same days-scale
phenomenon [[mean-reversion-spy-qqq]] tested directly on this data and
found no evidence for (Sharpe 0.023, mechanism-level test also null).
That prior null result doesn't bear on time-series momentum's validity —
different horizon, different (opposite) sign, different proposed cause
(underreaction/trend-following-crowd-driven drift at the month scale
rather than day-scale overreaction-and-snapback) — but it's the reason the
skip-month convention matters here: without it, the two effects would
partially cancel inside a single lookback window. [[dual-momentum]] uses
this same absolute test as a floor on top of [[cross-sectional-momentum]]'s
relative rank, so a basket-relative signal can go to cash instead of
always owning whichever candidate is least bad.

## Evidence & sources

- Moskowitz, Ooi, Pedersen (2012), "Time Series Momentum", *Journal of
  Financial Economics* — the original absolute-momentum construction this
  vault's [[tsmom-spy-qqq]] implementation follows (12-month lookback,
  1-month skip).
