# Telegram Bridge (P6)

Two-way control plane: owner-pinned commands in, event digests out.

## Why python-telegram-bot (not grammY)

One language across the agent-facing stack: the bridge shares the repo's
pydantic contracts and pytest tooling, agents can run its tests, and no Node
toolchain is required for a trading-critical component (Paperclip is the
only Node consumer, and it's non-critical by design). grammY is fine
software; the deciding factor is operational surface, not features.

## Security model

- **Allowlist of one.** `TELEGRAM_OWNER_ID` (your numeric user id) is
  pinned at startup; every update from any other id is dropped and logged,
  never processed.
- **Two-step live approvals.** `/approve <id>` on a paper→live promotion
  echoes the strategy, transition, rationale and evidence, then waits for
  the exact reply `CONFIRM <id>`. Anything else cancels. Both message ids
  land in `human_approval` (contract-enforced), written atomically
  (temp file + rename).
- Bot token and owner id come from the environment — never committed.

## Commands

| Command | Effect |
|---|---|
| `/status` | Kill-switch state, pending promotions, queue depth, paper results |
| `/halt` | Creates root `KILL` — all engines halt |
| `/resume` | Removes `KILL` |
| `/approve <id>` | One-step for non-live; two-step CONFIRM for live |
| `/reject <id>` | Moves the record to `data/promotions/rejected/` |
| free text | Filed to `infra/telegram/tasks/` for the research orchestrator |

## Outbound events

Agents drop `events.schema.json` instances into `infra/telegram/queue/`
(one file per event, filename = event id). The bridge polls every 5s:
`high`/`critical` are sent immediately; `info`/`warning` batch into a
digest flushed every 30 minutes. Processed events move to `queue/sent/`.

## Running

```sh
export TELEGRAM_BOT_TOKEN=...   # from @BotFather
export TELEGRAM_OWNER_ID=...    # your numeric id (@userinfobot)
cd infra/telegram && uv run telegram-bridge
```

## Deploy-time verification (the P6 "done when")

Logic is covered by `uv run pytest` (no token needed). On the WSL host with
real credentials, verify the round trip once:

1. `echo '{"schema_version":"1.0.0","id":"evt-smoke-1","source_agent":"manual","severity":"high","kind":"promotion_request","payload":{"text":"smoke test"},"requires_reply":true,"ts":"2026-01-01T00:00:00Z"}' > queue/evt-smoke-1.json`
   → phone pings within ~5s.
2. Seed a fake live promotion in `data/promotions/`, `/approve` it, reply
   `CONFIRM <id>` → record's `human_approval` is populated.
3. Start the paper engine (sim feed), `/halt` → engine stops at the next
   session boundary; `/resume` clears.
