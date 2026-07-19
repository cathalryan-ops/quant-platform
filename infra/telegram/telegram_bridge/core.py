"""Pure bridge logic — everything testable without a bot token.

Filesystem layout (all under the repo root):
- KILL                          kill switch (§2.3)
- data/promotions/<id>.json     pending promotion records (promotion contract)
- data/promotions/rejected/     rejected records (moved, never deleted)
- infra/telegram/queue/         outbound events, one JSON file per event
- infra/telegram/queue/sent/    processed events (moved, never deleted)
- infra/telegram/tasks/         free-text owner messages for the orchestrator
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

IMMEDIATE_SEVERITIES = {"high", "critical"}


def find_repo_root(start: Path) -> Path:
    for candidate in [start, *start.parents]:
        if (candidate / "contracts").is_dir() and (candidate / "CLAUDE.md").is_file():
            return candidate
    raise FileNotFoundError(f"no repo root above {start}")


def owner_id() -> int:
    """The single allowed Telegram user id. Everything else is dropped."""
    return int(os.environ["TELEGRAM_OWNER_ID"])


def is_owner(user_id: int | None) -> bool:
    return user_id is not None and user_id == owner_id()


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------- kill switch


def kill_path(repo_root: Path) -> Path:
    return repo_root / "KILL"


def halt(repo_root: Path, reason: str) -> None:
    kill_path(repo_root).write_text(f"{now_utc()} {reason}\n")


def resume(repo_root: Path) -> bool:
    """Remove the kill file; returns False if it wasn't there."""
    path = kill_path(repo_root)
    if not path.exists():
        return False
    path.unlink()
    return True


# ----------------------------------------------------------------- promotions


class ApprovalError(RuntimeError):
    pass


@dataclass
class PendingConfirmation:
    """A live /approve awaiting its CONFIRM <id> second step."""

    promotion_id: str
    approve_msg_id: int


def promotions_dir(repo_root: Path) -> Path:
    return repo_root / "data" / "promotions"


def load_promotion(repo_root: Path, promotion_id: str) -> dict:
    path = promotions_dir(repo_root) / f"{promotion_id}.json"
    if not path.exists():
        raise ApprovalError(f"no pending promotion {promotion_id!r}")
    return json.loads(path.read_text())


def describe_promotion(record: dict) -> str:
    """The echo message for the two-step confirmation."""
    scorecard = ", ".join(f"{k}={v}" for k, v in record.get("evidence_summary", {}).items())
    lines = [
        f"Promotion {record['id']}",
        f"strategy: {record['strategy_id']}",
        f"transition: {record['from_stage']} -> {record['to_stage']}",
        f"rationale: {record['rationale']}",
        f"evidence: {', '.join(record['evidence']) or 'none'}",
    ]
    if scorecard:
        lines.append(f"scorecard: {scorecard}")
    if record["to_stage"] == "live":
        lines.append(f"Reply exactly `CONFIRM {record['id']}` to approve. Anything else cancels.")
    return "\n".join(lines)


def start_approval(repo_root: Path, promotion_id: str, approve_msg_id: int) -> tuple[str, PendingConfirmation | None]:
    """Handle /approve. Non-live records are approved in one step; live
    records return a PendingConfirmation and the echo text (step one of two)."""
    record = load_promotion(repo_root, promotion_id)
    if record["to_stage"] != "live":
        _write_approval(repo_root, record, approve_msg_id, approve_msg_id)
        return (f"Approved {promotion_id} ({record['from_stage']} -> {record['to_stage']}).", None)
    return (describe_promotion(record), PendingConfirmation(promotion_id, approve_msg_id))


def confirm_approval(
    repo_root: Path, pending: PendingConfirmation, reply_text: str, confirm_msg_id: int
) -> str:
    """Step two: only the exact `CONFIRM <id>` reply approves."""
    expected = f"CONFIRM {pending.promotion_id}"
    if reply_text.strip() != expected:
        return f"Cancelled {pending.promotion_id} (expected `{expected}`)."
    record = load_promotion(repo_root, pending.promotion_id)
    _write_approval(repo_root, record, pending.approve_msg_id, confirm_msg_id)
    return f"LIVE promotion {pending.promotion_id} approved and recorded."


def _write_approval(repo_root: Path, record: dict, approve_msg_id: int, confirm_msg_id: int) -> None:
    """Atomically populate human_approval (write temp + rename)."""
    record["human_approval"] = {
        "required": True,
        "telegram_msg_id": approve_msg_id,
        "confirmation_msg_id": confirm_msg_id,
        "approved_at": now_utc(),
    }
    path = promotions_dir(repo_root) / f"{record['id']}.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(record, indent=2) + "\n")
    tmp.replace(path)


def reject_promotion(repo_root: Path, promotion_id: str) -> str:
    path = promotions_dir(repo_root) / f"{promotion_id}.json"
    if not path.exists():
        raise ApprovalError(f"no pending promotion {promotion_id!r}")
    rejected = promotions_dir(repo_root) / "rejected"
    rejected.mkdir(parents=True, exist_ok=True)
    path.replace(rejected / path.name)
    return f"Rejected {promotion_id} (record moved to promotions/rejected/)."


# --------------------------------------------------------------- event queue


def queue_dir(repo_root: Path) -> Path:
    return repo_root / "infra" / "telegram" / "queue"


def scan_queue(repo_root: Path) -> tuple[list[dict], list[dict]]:
    """Returns (immediate, batchable) events, oldest first, each with a
    '_path' key for mark_sent. Malformed files are skipped, not deleted."""
    qdir = queue_dir(repo_root)
    immediate: list[dict] = []
    batchable: list[dict] = []
    if not qdir.exists():
        return immediate, batchable
    for path in sorted(p for p in qdir.iterdir() if p.suffix == ".json" and p.is_file()):
        try:
            event = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        event["_path"] = str(path)
        target = immediate if event.get("severity") in IMMEDIATE_SEVERITIES else batchable
        target.append(event)
    return immediate, batchable


def format_event(event: dict) -> str:
    sev = event.get("severity", "info").upper()
    text = event.get("payload", {}).get("text") or json.dumps(event.get("payload", {}))
    return f"[{sev}] {event.get('source_agent', '?')}/{event.get('kind', '?')}: {text}"


def format_digest(events: list[dict]) -> str:
    return "Digest:\n" + "\n".join(f"- {format_event(e)}" for e in events)


def mark_sent(event: dict) -> None:
    path = Path(event["_path"])
    sent = path.parent / "sent"
    sent.mkdir(parents=True, exist_ok=True)
    path.replace(sent / path.name)


# ---------------------------------------------------------------- free text


def file_task(repo_root: Path, text: str, msg_id: int) -> Path:
    """Route a free-text owner message to the orchestrator's task queue."""
    tasks = repo_root / "infra" / "telegram" / "tasks"
    tasks.mkdir(parents=True, exist_ok=True)
    stamp = re.sub(r"[^0-9T]", "", now_utc())
    path = tasks / f"task-{stamp}-{msg_id}.json"
    path.write_text(
        json.dumps({"received_at": now_utc(), "telegram_msg_id": msg_id, "text": text}, indent=2)
        + "\n"
    )
    return path


# ------------------------------------------------------------------- status


def status_text(repo_root: Path) -> str:
    killed = kill_path(repo_root).exists()
    pending = (
        sorted(p.stem for p in promotions_dir(repo_root).glob("*.json"))
        if promotions_dir(repo_root).exists()
        else []
    )
    immediate, batchable = scan_queue(repo_root)
    results = sorted(p.parent.name for p in repo_root.glob("data/results/*/paper_result.json"))
    return "\n".join(
        [
            f"kill switch: {'ACTIVE — trading halted' if killed else 'clear'}",
            f"pending promotions: {', '.join(pending) or 'none'}",
            f"queued events: {len(immediate)} immediate, {len(batchable)} batchable",
            f"strategies with paper results: {', '.join(results) or 'none'}",
        ]
    )
