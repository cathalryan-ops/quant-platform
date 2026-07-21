---
type: concept
created: 2026-07-21
---

# Volatility Targeting

Scale position size continuously and inversely with trailing realized
volatility, so exposure shrinks smoothly as markets get more turbulent
and grows back smoothly as they calm down — `size = min(1.0,
vol_target / realized_vol)` in this vault's long-only, no-leverage v1
form (never scales above the base signal's own weight, only below it).
The standard sizing overlay behind most CTA and risk-parity strategies.

## What matters for us

Distinct from both [[ms-shift-spy-vol-regime]]'s absolute-band gate and
[[volatility-acceleration]]'s relative-ratio gate: those are both
*binary* (long or flat), so they necessarily have a threshold to cross,
and every crossing pays a discrete round-trip trading cost. Volatility
targeting has no threshold at all — position size is a continuous
function of realized vol, so it can de-risk gradually without ever fully
closing a position on an ordinary volatile-but-not-crisis day. Motivated
directly by [[tsmom-vol-accel-hysteresis]]'s finding that even hysteresis
only trimmed a binary gate's turnover cost at the margin — the deeper
question this raises is whether the *binary* framing itself, not just a
particular threshold choice, was the wrong lever.

## Evidence & sources

- Motivating gap identified directly in this vault —
  [[tsmom-vol-accel-hysteresis]]'s Lifecycle history (2026-07-21
  retirement).
