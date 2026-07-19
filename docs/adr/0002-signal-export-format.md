# ADR 0002 — Python→Rust signal handoff: parameterised rulesets

**Status:** accepted 2026-07-19 · **Owner:** P5 (consumed by P4, P8)

## Context

Backtests fit signals in Python; the paper/live engines are Rust and must
keep Python out of the execution path. The spec's options were parameterised
rulesets (Rust interprets fitted parameters) or embedding (PyO3).

## Decision

Parameterised rulesets. The backtest stage exports
`data/results/<strategy-id>/ruleset.json`:

```json
{
  "schema_version": "1.0.0",
  "strategy_id": "sma-cross-test-v1",
  "family": "swing",
  "max_position_pct": 5.0,
  "params": { "type": "sma_cross", "fast": 20, "slow": 50 },
  "data_snapshot": { "parquet_path": "...", "content_hash": "sha256:...", "source_feed": "...", "period": {"start": "...", "end": "..."} }
}
```

- `params` is a tagged union; each `type` has a Rust interpreter in
  `engine-core::engine::ruleset` producing target long weights in [0, 1]
  per symbol from a rolling close-price window — the same semantics as the
  Python `Signal` protocol.
- `data_snapshot` carries the provenance of the fit; the paper engine
  copies it into every `paper_result.json` (contract requirement).
- v1 ships one interpreter, `sma_cross` (the acceptance strategy). Each new
  strategy family adds a `params` variant + interpreter + a golden test
  pinning Python and Rust outputs to each other.

## Rejected: PyO3 embedding

Puts a Python runtime inside the reliability-critical process, couples
deploys, and buys nothing at daily cadence. Reconsider only if strategies
outgrow what parameter vectors can express (e.g. learned models) — per the
architecture doc §9.
