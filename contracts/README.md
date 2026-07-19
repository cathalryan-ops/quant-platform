# Contracts

The shared schemas every workstream codes against — the parallelisation
keystone. No component may depend on another workstream's internals; all
cross-component data flows validate against these files.

## Files

| Schema | Instance produced by | Consumed by |
|---|---|---|
| `strategy_manifest.schema.json` | Research agents (embedded in wiki strategy pages) | Backtester, paper engine, ranker, live engine |
| `backtest_result.schema.json` | Backtest harness (`sandbox/backtest`) | Ranker, postmortem analyst |
| `paper_result.schema.json` | Paper engine (`sandbox/paper-engine`) | Ranker, postmortem analyst |
| `promotion.schema.json` | Ranker | Live engine, Telegram bridge, wiki |
| `events.schema.json` | Everyone | Telegram bridge, dashboard |

`promotion_thresholds.toml` (same directory) holds the ranker's promotion
criteria — **human-editable only**, agent-readable.

## Versioning

- Every schema carries a semver in its `$id`
  (`https://quant-platform.invalid/contracts/<name>/<version>`), and every
  instance carries a matching `schema_version` field.
- **Breaking changes require a new version — never mutate a published
  schema.** Add the new file alongside the old one and migrate consumers
  deliberately.

## Typed mirrors

- **Rust:** `engine-core/src/contracts.rs` (serde + schemars,
  `deny_unknown_fields`).
- **Python:** `sandbox/backtest/contracts.py` (pydantic v2, `extra="forbid"`).

Both are kept in lockstep with the schemas by round-trip tests over
`examples/` — one example instance per schema:

```sh
cargo test -p engine-core                    # Rust: parse -> serialize -> identical JSON
cd sandbox/backtest && uv run pytest         # Python: schema validation + round-trip
```

## Constraints that live at runtime, not in the type system

The schemas/types cannot express these; every consumer re-checks them:

1. `market: "polymarket"` is schema-valid but **rejected by all v1 runtime
   components** (reserved for v2).
2. `risk.max_position_pct` must not exceed the `live/guardrails.toml` cap.
3. A promotion with `to_stage: "live"` requires a complete two-step
   `human_approval` (`telegram_msg_id`, `confirmation_msg_id`, `approved_at`
   all set). The promotion schema enforces this shape via `if/then`, and
   both mirrors expose `is_complete()` — the live engine must call it before
   acting regardless.
4. Results whose `data_snapshot.content_hash` no longer matches the parquet
   file on disk are invalid; the ranker ignores them.
