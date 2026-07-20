# Automation — what's install-ready vs. still manual (P10)

This is the plain-English companion to `infra/paperclip/` and `infra/cron/`.
It answers one question: **if you install this on the real WSL host today,
what actually runs, and what still needs a human?**

Everything here mirrors Paperclip's org chart/heartbeats as plain cron so
trading-critical jobs survive the dashboard being down (see
`infra/paperclip/README.md` and `docs/architecture.md` §6 P10). Nothing in
this repo installs, starts, or schedules anything on its own — you install
it explicitly, once, on your persistent host.

## (a) Ready to install as-is

Two jobs in `infra/cron/crontab.generated` have real, working commands today
and can be installed on the real WSL host right now:

| Job | Command | Verified against |
|---|---|---|
| Ranker (promotion pipeline) | `cd $QP/sandbox/backtest && uv run ranker` | `[project.scripts] ranker = "ranker:main"` in `sandbox/backtest/pyproject.toml` |
| Telegram bridge liveness (restart-if-dead, every 5 min) | `cd $QP/infra/telegram && nohup uv run telegram-bridge >> bridge.log 2>&1 &` | `[project.scripts] telegram-bridge = "telegram_bridge.bot:main"` in `infra/telegram/pyproject.toml` |

Both go through `infra/cron/run_agent.sh`, so they:
- no-op and log `SKIPPED (loop frozen)` if `infra/paperclip/FROZEN` exists,
- no-op and log `SKIPPED (KILL present)` if `<repo-root>/KILL` exists,
- log `START` / `OK` / `FAILED rc=<n>` to `infra/paperclip/audit.log`
  otherwise.

Both gating paths were dry-run tested during this verification pass
(create `FROZEN` → confirm `SKIPPED` logged → delete `FROZEN` → confirm
`START`/`OK` logged) with no state or log lines left behind afterward.

To install:

```sh
crontab infra/cron/crontab.generated
```

This **replaces** your existing crontab wholesale — review your current
`crontab -l` first if you have unrelated jobs on this host, and merge by
hand if so.

Regenerate the file before installing (the NYSE calendar shifts with DST,
and pre-open/post-close times are computed, never hardcoded):

```sh
cd sandbox/backtest && uv run python ../../infra/cron/compute_schedule.py
```

## (b) Still a manual TODO, and why

Three heartbeats in `company.json` are Claude-prompt-driven agents
(`research-orchestrator`, `postmortem-analyst`, `vault-ops`'s `/lint` +
`/digest`) — their "work" is a Claude Code prompt (`agents/*.md` or a
`.claude/skills/*/SKILL.md`), not a CLI binary or Python entrypoint this
repo vendors. **There is genuinely no headless Claude Code invocation
mechanism wired up in this repo yet.** `crontab.generated` is honest about
this: each of the three has a real cron line at the correct computed time,
through `run_agent.sh` (so freeze/kill gating and audit logging already
work for them), but the payload is a labeled stub:

```
$QP/infra/cron/run_agent.sh research-orchestrator echo "TODO: claude -p agents/research-orchestrator.md"
$QP/infra/cron/run_agent.sh postmortem-analyst    echo "TODO: claude -p agents/postmortem-analyst.md"
$QP/infra/cron/run_agent.sh vault-ops             echo "TODO: claude -p /lint then /digest"
```

Running these today just logs the stub `echo` to the audit trail — it does
**not** run the orchestrator, the postmortem analyst, or vault lint/digest.
Do not treat a green `OK` in `audit.log` for these three roles as evidence
the underlying work happened.

This is not a bug to patch with a fabricated command; it's an open decision
the user hasn't made yet. Closing it needs one of:

1. **Paperclip's own scheduler** fires these roles directly (its native
   heartbeat/container execution, per `infra/paperclip/README.md` step 2) —
   in which case the cron stub lines above stay as a dashboard-down
   fallback and can stay stubs, or
2. A real `claude -p <prompt-file>` (or Claude Agent SDK) wiring decision —
   headless auth, working-directory/mount strategy, and output capture into
   `brain/` / the audit trail — which does not exist in this repo yet and
   needs its own design pass before it's cron-safe.

Either way, **do not invent a working command for these three** until one
of the two paths above is actually decided and tested. `postmortem-analyst`
in particular was missing a cron line entirely before this pass (the
template comment referenced it, the generated file didn't); it's now
present as an honest stub alongside the other two, not silently dropped.

## (c) When you're ready to install this for real — checklist

- [ ] Copy `.env.example` to `.env` at repo root and fill in
      `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`, `TELEGRAM_BOT_TOKEN`,
      `TELEGRAM_OWNER_ID` (see `docs/RUNBOOK.md` §0). Both
      `infra/telegram` and `sandbox/backtest` auto-load this file via
      `python-dotenv`; a real exported env var always wins over it.
      `QP_REAL_TRADING` is the separate real-money gate — leave it unset
      until you mean it (see `docs/RUNBOOK.md` §5).
- [ ] Run `cd sandbox/backtest && uv run python ../../infra/cron/compute_schedule.py`
      on the host itself (times are computed from the calendar at
      generation time, so regenerate on the host, don't copy a stale file
      from elsewhere).
- [ ] `git status` on `infra/cron/crontab.generated` — confirm the times
      look right for today's date before installing.
- [ ] Review your existing `crontab -l` for unrelated jobs, then
      `crontab infra/cron/crontab.generated`.
- [ ] Confirm `<repo-root>/KILL` does **not** exist and
      `infra/paperclip/FROZEN` does **not** exist (both are runtime state,
      not config — neither should be committed).
- [ ] Start the Telegram bridge once by hand the first time
      (`cd infra/telegram && uv run telegram-bridge`) and confirm `/status`
      replies, so the liveness cron job has something to detect if it dies
      later.
- [ ] Install Paperclip itself per its own docs (not vendored in this
      repo) and follow `infra/paperclip/README.md` to recreate the org
      chart from `company.json` and wire `on_budget_exhausted.sh` as its
      budget-exhausted hook.
- [ ] Decide and implement the headless Claude invocation path from
      section (b) above before treating `research-orchestrator`,
      `postmortem-analyst`, or `vault-ops` cron `OK` lines as real work
      done.
- [ ] `tail -f infra/paperclip/audit.log` after the first scheduled fire to
      confirm `START`/`OK` (or `SKIPPED`, if you're testing the freeze
      gate) lines are landing as expected.

## Status summary

**What works if you install this today:** the ranker (promotion pipeline)
and the Telegram bridge liveness check are real, tested commands that run
through the freeze/kill-gated, audit-logged wrapper — install the crontab
and they do real work on schedule. **What's still manual:** the research
orchestrator, postmortem analyst, and vault `/lint`+`/digest` heartbeats
have correctly-timed cron slots and audit-trail plumbing, but their payload
is an honest `TODO` stub — there's no headless Claude Code invocation
mechanism in this repo yet, and closing that gap is a design decision
(Paperclip-native scheduling vs. a real `claude -p` wiring) the user needs
to make, not something to fabricate a working command for.
