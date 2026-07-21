---
type: concept
created: 2026-07-19
---

# Market Structure Shift

A market structure shift is a decisive break of the most recent swing point
against the prevailing swing sequence on a chart — for example, after a
series of lower highs, a close above the last lower high. It marks the
point where the prior trend's structure is no longer intact.

## What matters for us

This is the core setup of the v1 `ms_shift` strategy family. Two claims to
test, per the source: (1) daily-chart shifts are meaningfully rarer and
cleaner than lower-timeframe ones, and (2) shifts accompanied by
[[displacement]] precede multi-day continuation — i.e., they are swing
signals, not precise entries. The claimed mechanism is forced exits by
traders anchored to the old trend fueling the move. Day-scale event-driven
and structurally unrelated to [[time-series-momentum]]'s month-scale
trailing return — the pairing [[tsmom-ms-shift-blend]] tests via
[[signal-blending]].

## Evidence & sources

- Definition, displacement qualifier, and continuation claim —
  [market structure primer](../../raw/sample-market-structure-primer.md)
