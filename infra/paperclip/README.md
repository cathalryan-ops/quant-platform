# Paperclip — orchestration dashboard (P10)

Paperclip (self-hosted Node server + React UI) is the management layer:
org chart, per-agent budgets, heartbeats, audit trail with token cost. It
is deliberately **non-critical**: every trading-critical schedule is
mirrored as plain cron (`infra/cron/`), so the dashboard being down never
stops the loop.

## Setup (WSL host)

1. Install Paperclip per its own docs and point a company at this repo.
2. Recreate the org from `company.json` in Paperclip's native
   company/budget layout: Opus managers (research-orchestrator, ranker),
   Sonnet/Haiku executors reporting to them, with the monthly budgets and
   heartbeat names listed there. Use its standard containerized execution
   environment for agent runs, mounting this repo read-write.
3. Wire the budget-exhausted hook to `on_budget_exhausted.sh <role>` —
   this implements the ratified policy: ONE agent over budget freezes the
   ENTIRE loop (`infra/paperclip/FROZEN`) and sends a critical Telegram
   event. Resume by deleting the FROZEN file.
4. Route every agent run through `infra/cron/run_agent.sh <role> <cmd>` so
   the FROZEN/KILL gates apply and runs land in `audit.log` even when they
   start from the dashboard.

## Heartbeats

Defined once in `company.json`, mirrored in cron. Times come from the NYSE
calendar via `infra/cron/compute_schedule.py` (pandas_market_calendars) —
regenerate after DST changes; never hardcode UTC hours.

| Heartbeat | Schedule | Runs |
|---|---|---|
| pre_us_open_daily | NYSE open − 90 min, Mon–Fri | research orchestrator |
| post_us_close_daily | NYSE close + 60 min, Mon–Fri | ranker (`uv run ranker`), postmortem analyst |
| nightly | 03:00 UTC | vault `/lint` + `/digest` |

## Done-when checklist (needs the real dashboard)

- [ ] Org chart visible with the five roles and reporting lines
- [ ] A heartbeat fires the research orchestrator inside a container
- [ ] Token spend per agent visible in the audit trail
- [ ] Simulated budget exhaustion (run `on_budget_exhausted.sh test`) freezes
      the loop (`run_agent.sh` skips) and pings Telegram
