---
type: concept
created: 2026-07-21
---

# Dual Momentum

Combine [[time-series-momentum]]'s absolute test ("is this asset's own
trailing trend positive?") with [[cross-sectional-momentum]]'s relative
test ("which asset in the basket is winning?") into a single rule: hold
the basket's relative leader, but only if that leader also clears its own
absolute-momentum floor — otherwise go to cash. Antonacci's "Dual
Momentum" (2014) popularized this exact composition (equities vs. bonds,
switch to bonds or cash when equities' own trend turns negative) as a
flight-to-quality overlay, not just a relative-strength bet.

## What matters for us

Every basket-relative hypothesis in this vault so far
([[cross-sectional-momentum]] via [[sector-rotation]]) ranks within a
single asset class (10 equity sector ETFs) — the relative leader is
always *some* sector, even in a broad drawdown, because the ranking never
asks whether being long anything at all is a good idea. Dual momentum's
absolute floor is the mechanism that lets a cross-sectional signal go
flat: it isn't just "own whichever sector is least bad," it's "own the
best asset in the basket, unless the basket itself is broadly
unattractive, in which case own nothing." That only means something when
the basket spans genuinely different risk regimes — equities, long
bonds, gold — which is exactly what the 16-symbol snapshot's SPY/TLT/GLD
subset is for. The causal story is also distinct from pure sector
rotation: not intra-asset-class capital reallocation, but a cross-asset
flight-to-quality reallocation during equity drawdowns (the well-known
empirical tendency for bonds and/or gold to hold up or rally when
equities sell off hard).

## Evidence & sources

- Antonacci, G. (2014), *Dual Momentum Investing* — the original
  absolute-floor + relative-rank composition this vault's
  [[dual-momentum-equity-bond-gold]] implementation follows.
