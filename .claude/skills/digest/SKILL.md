---
name: digest
description: Synthesise what changed in the vault since the last digest — new pages, lifecycle transitions, scorecard moves, open questions — into one events-contract digest for Telegram. Run nightly.
---

# /digest

1. Find the last `digest` line in `brain/log.md`; everything after it is
   the window (first run: whole log).
2. Summarise the window in ONE paragraph: pages added/extended, strategy
   lifecycle transitions, scorecard changes, postmortems filed, plus the
   single most interesting open question in the vault right now.
3. Emit it as an `events.schema.json` instance: `severity: "info"`,
   `kind: "daily_digest"`, `requires_reply: false`, payload
   `{"text": "<paragraph>"}` — written to the Telegram bridge's queue
   (`infra/telegram/queue/`, one JSON file per event, filename = event id).
4. Append `- YYYY-MM-DD — digest — <n> changes summarised` to `log.md`.
5. If nothing changed, emit nothing and log `digest — no changes`.
