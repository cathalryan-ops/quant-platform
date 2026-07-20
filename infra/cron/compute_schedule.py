"""Regenerate crontab entries from the real NYSE calendar (never hardcode
UTC hours — DST moves them). Run monthly, or whenever the clocks change:

    cd sandbox/backtest && uv run python ../../infra/cron/compute_schedule.py

Writes infra/cron/crontab.generated; install with `crontab crontab.generated`.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pandas_market_calendars as mcal

ROOT = Path(__file__).resolve().parents[2]

TEMPLATE = """\
# quant-platform schedules — GENERATED {today} from the NYSE calendar.
# Mirrors Paperclip heartbeats so trading-critical jobs survive the
# dashboard being down. All jobs go through run_agent.sh (freeze/kill gates
# + audit log).
SHELL=/bin/bash
QP={root}

# Research orchestrator: daily, NYSE open minus 90 minutes ({pre_open} UTC)
{pre_open_min} {pre_open_hour} * * 1-5 $QP/infra/cron/run_agent.sh research-orchestrator echo "TODO: claude -p agents/research-orchestrator.md"

# Ranker: NYSE close plus 60 minutes ({post_close} UTC)
{post_close_min} {post_close_hour} * * 1-5 $QP/infra/cron/run_agent.sh ranker bash -c 'cd $QP/sandbox/backtest && uv run ranker'

# Postmortem analyst: same heartbeat as ranker (NYSE close plus 60 minutes,
# {post_close} UTC). No headless Claude Code invocation is wired up yet —
# this is a manual/TODO stub, not a working command. See docs/AUTOMATION.md.
{post_close_min} {post_close_hour} * * 1-5 $QP/infra/cron/run_agent.sh postmortem-analyst echo "TODO: claude -p agents/postmortem-analyst.md"

# Vault hygiene: /lint + /digest nightly 03:00 UTC
0 3 * * * $QP/infra/cron/run_agent.sh vault-ops echo "TODO: claude -p /lint then /digest"

# Telegram bridge liveness (restart if dead) every 5 minutes
*/5 * * * * pgrep -f telegram-bridge > /dev/null || (cd $QP/infra/telegram && nohup uv run telegram-bridge >> bridge.log 2>&1 &)
"""


def main() -> None:
    nyse = mcal.get_calendar("NYSE")
    today = dt.date.today()
    sched = nyse.schedule(start_date=today, end_date=today + dt.timedelta(days=14))
    first = sched.iloc[0]
    open_utc = first["market_open"].tz_convert("UTC")
    close_utc = first["market_close"].tz_convert("UTC")
    pre = open_utc - dt.timedelta(minutes=90)
    post = close_utc + dt.timedelta(minutes=60)

    out = ROOT / "infra/cron/crontab.generated"
    out.write_text(
        TEMPLATE.format(
            today=today.isoformat(),
            root=ROOT,
            pre_open=pre.strftime("%H:%M"),
            pre_open_min=pre.minute,
            pre_open_hour=pre.hour,
            post_close=post.strftime("%H:%M"),
            post_close_min=post.minute,
            post_close_hour=post.hour,
        )
    )
    print(f"wrote {out} (open {open_utc.strftime('%H:%M')} UTC, close {close_utc.strftime('%H:%M')} UTC)")


if __name__ == "__main__":
    main()
