#!/usr/bin/env python3
"""Single-shot health check: Alpaca connectivity + live engine heartbeat
staleness. Invoked externally every 5 minutes (see
infra/cron/crontab.generated) — this is NOT a long-running loop itself.

On failure, drops a critical-severity event into infra/telegram/queue/ —
the telegram bridge's pump_queue job (infra/telegram/telegram_bridge/bot.py)
already delivers critical/high-severity queue events immediately, so this
reuses that path rather than talking to Telegram directly.

The staleness check reads live/heartbeat.json (written by live/src/session.rs
independently of session-processing cadence — the real feed is a daily-bar
WebSocket stream that can idle for hours between legitimate trading days, so
"time since last session" alone can't distinguish that from a genuine stall).
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

STALE_AFTER = dt.timedelta(minutes=5)
ALPACA_PAPER_BASE = "https://paper-api.alpaca.markets"


def find_repo_root(start: Path) -> Path:
    for candidate in [start, *start.parents]:
        if (candidate / "contracts").is_dir() and (candidate / "CLAUDE.md").is_file():
            return candidate
    raise FileNotFoundError(f"no repo root above {start}")


def _load_env(repo_root: Path) -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    env_path = repo_root / ".env"
    if env_path.is_file():
        load_dotenv(env_path, override=False)


def check_alpaca_connectivity(timeout: float = 10.0) -> tuple[bool, str]:
    """Returns (ok, detail). A missing key is reported as not-ok, never raised."""
    key = os.environ.get("ALPACA_API_KEY")
    secret = os.environ.get("ALPACA_SECRET_KEY")
    if not key or not secret:
        return False, "ALPACA_API_KEY/ALPACA_SECRET_KEY not set"
    req = urllib.request.Request(
        f"{ALPACA_PAPER_BASE}/v2/clock",
        headers={"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                return True, "ok"
            return False, f"unexpected status {resp.status}"
    except urllib.error.URLError as e:
        return False, f"connection failed: {e}"
    except TimeoutError:
        return False, "timed out"


def heartbeat_staleness(repo_root: Path, now: dt.datetime) -> tuple[bool, str]:
    """Returns (stale, detail). A missing heartbeat file counts as stale —
    the engine has never reported in, which is exactly the failure mode
    this exists to catch, not a reason to skip the check."""
    path = repo_root / "live" / "heartbeat.json"
    if not path.is_file():
        return True, f"{path} does not exist — engine has never reported a heartbeat"
    try:
        data = json.loads(path.read_text())
        last_alive_at = dt.datetime.strptime(
            data["last_alive_at"], "%Y-%m-%dT%H:%M:%SZ"
        ).replace(tzinfo=dt.timezone.utc)
    except (OSError, json.JSONDecodeError, KeyError, ValueError) as e:
        return True, f"heartbeat file unreadable/malformed: {e}"
    age = now - last_alive_at
    if age > STALE_AFTER:
        return True, (
            f"last heartbeat {age.total_seconds():.0f}s ago "
            f"(> {STALE_AFTER.total_seconds():.0f}s)"
        )
    return False, f"last heartbeat {age.total_seconds():.0f}s ago"


def emit_critical_event(repo_root: Path, kind: str, text: str, now: dt.datetime) -> Path:
    """Matches the Event contract in sandbox/backtest/contracts.py exactly —
    the same shape infra/telegram/telegram_bridge/core.py's scan_queue parses."""
    ts = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    event_id = f"evt-health-{kind.replace('_', '-')}-{now.strftime('%Y%m%d%H%M%S%f')}"
    event = {
        "schema_version": "1.0.0",
        "id": event_id,
        "source_agent": "health-check",
        "severity": "critical",
        "kind": kind,
        "payload": {"text": text},
        "requires_reply": False,
        "ts": ts,
    }
    qdir = repo_root / "infra" / "telegram" / "queue"
    qdir.mkdir(parents=True, exist_ok=True)
    path = qdir / f"{event_id}.json"
    path.write_text(json.dumps(event, indent=2) + "\n")
    return path


def run(repo_root: Path, now: dt.datetime | None = None) -> int:
    """Returns a process exit code (0 healthy, 1 something alerted)."""
    now = now or dt.datetime.now(dt.timezone.utc)
    alpaca_ok, alpaca_detail = check_alpaca_connectivity()
    stale, stale_detail = heartbeat_staleness(repo_root, now)

    if not alpaca_ok:
        emit_critical_event(repo_root, "alpaca_disconnected", alpaca_detail, now)
        print(f"ALERT: Alpaca disconnected — {alpaca_detail}")
    if stale:
        emit_critical_event(repo_root, "engine_stalled", stale_detail, now)
        print(f"ALERT: engine heartbeat stale — {stale_detail}")
    if alpaca_ok and not stale:
        print(f"ok — alpaca: {alpaca_detail}; heartbeat: {stale_detail}")
    return 0 if (alpaca_ok and not stale) else 1


def main() -> int:
    repo_root = find_repo_root(Path(__file__).resolve().parent)
    _load_env(repo_root)
    return run(repo_root)


if __name__ == "__main__":
    sys.exit(main())
