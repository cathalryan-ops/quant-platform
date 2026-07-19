# quant-platform

Agentic quant trading platform: US-equity swing / market-structure-shift
strategies on a daily timescale, with a Rust execution engine (uptime and
deterministic risk, not latency), Python backtesting, an Obsidian knowledge
vault, and Telegram-gated live promotions.

**Start here: [`docs/architecture.md`](docs/architecture.md)** — the full
specification, trading mandate, safety rules, and the delegated prompt plan
(P0–P11). `CLAUDE.md` is the agent constitution every agent inherits.

## Layout

| Path | What |
|---|---|
| `brain/` | Obsidian vault — research wiki, strategy pages, postmortems |
| `contracts/` | JSON Schemas + promotion thresholds — the seam between all workstreams |
| `sandbox/backtest/` | Python (uv) backtest harness |
| `sandbox/paper-engine/` | Rust paper-execution engine (no broker order client, by construction) |
| `live/` | Rust real-stakes engine + `guardrails.toml` (human-editable only) |
| `engine-core/` | Shared Rust types mirroring the contracts |
| `agents/` | One prompt file per delegated role |
| `infra/` | Paperclip, Telegram bridge, cron, dashboard glue |

## Safety spine

Root `KILL` file halts everything · `guardrails.toml` is enforced inside the
order path · paper→live promotion always requires a two-step Telegram
approval · live keys exist only in the `live/` process environment.

## Build

```sh
cargo check                                  # Rust workspace
cd sandbox/backtest && uv run pytest         # Python harness
```
