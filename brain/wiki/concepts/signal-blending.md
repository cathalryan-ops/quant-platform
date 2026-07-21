---
type: concept
created: 2026-07-21
---

# Signal Blending

Combine two or more structurally independent trading signals by averaging
their position weights, rather than using one to gate or filter another.
Every conditioning layer this vault has tested so far ([[market-breadth]],
[[volatility-acceleration]], [[volatility-targeting]]) took one signal and
multiplied it by a second, independently-computed factor that can only
ever REMOVE exposure — a gate's output is bounded above by the base
signal's own weight, never higher. Blending is structurally different: it
doesn't let one signal veto another, it treats each as an independent
source of edge and averages their already-fully-formed position
decisions, so a day when only one of the two is long still gets partial
exposure (e.g. 0.5, not 0) rather than the absent signal cancelling the
position outright.

## What matters for us

Classical portfolio theory (Markowitz 1952): if two return streams have
less-than-perfect correlation, a blend of the two can have a HIGHER Sharpe
than either alone, because portfolio variance falls faster than the
average of expected returns does as correlation drops below 1.0. This only
pays off if the two signals are meaningfully independent — highly
correlated signals blend to something close to either one alone (or worse,
dilute the stronger one with the weaker one's noise, with no diversification
benefit to offset it). Every gate tried on [[time-series-momentum]]
([[tsmom-spy-qqq]]) so far made it worse, which rules out conditioning-as-a-
veto as a lever on this specific signal/data — but says nothing about
whether *combining* it with a second, independently-timed edge would help,
since that's a different mechanism (addition of a second return source,
not restriction of the first one). [[tsmom-spy-qqq]] and
[[market-structure-shift]]'s [[ms-shift-spy-high-displacement]] are the
natural first pair to test this on: unrelated signal constructions (a
month-scale trailing return vs. a day-scale swing-break-plus-displacement
event) that independently converged on the same headline Sharpe (0.813) —
suggestive of, but not proof of, low correlation.
[[tsmom-ms-shift-blend]] measures the actual correlation between the two
return streams directly rather than assuming it from the coincidence.

## Evidence & sources

- Markowitz, H. (1952), "Portfolio Selection", *Journal of Finance* — the
  standard diversification argument motivating [[tsmom-ms-shift-blend]].
- Motivating null result: `research-campaign-2026-07-21` postmortem's
  finding that three separate gate-style (veto-only) combinations all
  reduced [[tsmom-spy-qqq]]'s Sharpe rather than improving it.
