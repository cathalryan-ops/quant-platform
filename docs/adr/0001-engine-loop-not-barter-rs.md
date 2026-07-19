# ADR 0001 — Thin tokio loop instead of barter-rs

**Status:** accepted 2026-07-19 · **Owner:** P5

## Context

The spec requires evaluating barter-rs before building an engine loop.
barter-rs is an event-driven live/backtest trading framework built around
streaming market events, its own engine/portfolio/execution abstractions,
and latency-conscious design.

## Decision

Do not adopt barter-rs for v1. Build a thin tokio loop over our own types.

## Rationale

1. Our mandate is daily/swing only: the engine's unit of work is
   "end-of-session bar arrives → recompute target weights → simulate/submit
   orders → journal state". That is tens of events per day, not a streaming
   hot path — the part of barter-rs that carries its value is the part we
   would not use.
2. The platform's spine is the contracts + state journal + guardrails.
   Mapping those through barter-rs's own portfolio/execution abstractions
   adds a translation layer in exactly the code that must stay auditable.
3. The paper engine's no-broker-dependency invariant (enforced by not
   depending on any order-submission client) is simplest to prove when the
   dependency tree is minimal.

## Consequences

- We own ~300 lines of loop/executor code and their tests.
- Revisit if v2 adds intraday execution or multi-venue routing — that is
  the regime barter-rs is built for. This ADR is the justification the
  spec requires for not building on it.
