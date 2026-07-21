"""Offline tests for infra/health_check.py. No real network access —
Alpaca connectivity is stubbed via monkeypatch, never actually called."""

import datetime as dt
import importlib.util
import json
from pathlib import Path

# Load by file path rather than sys.path.insert(infra/) + `import health_check`:
# infra/telegram/ is a directory with no __init__.py, so adding infra/ to
# sys.path makes it resolve as an implicit namespace package named
# `telegram` — which then shadows the real `telegram` (python-telegram-bot)
# package for the rest of the pytest process, breaking vectorbt's optional
# `import telegram` messaging integration in any test file that later runs
# `import vectorbt` in the same session.
_spec = importlib.util.spec_from_file_location(
    "health_check", Path(__file__).resolve().parents[1] / "health_check.py"
)
hc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hc)


def write_heartbeat(repo_root: Path, when: dt.datetime) -> None:
    live_dir = repo_root / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    (live_dir / "heartbeat.json").write_text(
        json.dumps({"last_alive_at": when.strftime("%Y-%m-%dT%H:%M:%SZ")})
    )


def test_heartbeat_missing_file_counts_as_stale(tmp_path):
    now = dt.datetime(2026, 7, 20, tzinfo=dt.timezone.utc)
    stale, detail = hc.heartbeat_staleness(tmp_path, now)
    assert stale is True
    assert "does not exist" in detail


def test_heartbeat_fresh_is_not_stale(tmp_path):
    now = dt.datetime(2026, 7, 20, 12, 0, 0, tzinfo=dt.timezone.utc)
    write_heartbeat(tmp_path, now - dt.timedelta(minutes=2))
    stale, detail = hc.heartbeat_staleness(tmp_path, now)
    assert stale is False
    assert "120s ago" in detail


def test_heartbeat_older_than_five_minutes_is_stale(tmp_path):
    now = dt.datetime(2026, 7, 20, 12, 0, 0, tzinfo=dt.timezone.utc)
    write_heartbeat(tmp_path, now - dt.timedelta(minutes=6))
    stale, detail = hc.heartbeat_staleness(tmp_path, now)
    assert stale is True
    assert "360s ago" in detail


def test_heartbeat_exactly_at_threshold_is_not_stale(tmp_path):
    now = dt.datetime(2026, 7, 20, 12, 0, 0, tzinfo=dt.timezone.utc)
    write_heartbeat(tmp_path, now - dt.timedelta(minutes=5))
    stale, _ = hc.heartbeat_staleness(tmp_path, now)
    assert stale is False


def test_heartbeat_malformed_json_counts_as_stale(tmp_path):
    live_dir = tmp_path / "live"
    live_dir.mkdir(parents=True)
    (live_dir / "heartbeat.json").write_text("not json")
    stale, detail = hc.heartbeat_staleness(tmp_path, dt.datetime.now(dt.timezone.utc))
    assert stale is True
    assert "malformed" in detail


def test_emit_critical_event_matches_the_existing_contract(tmp_path):
    now = dt.datetime(2026, 7, 20, 12, 0, 0, tzinfo=dt.timezone.utc)
    path = hc.emit_critical_event(tmp_path, "engine_stalled", "detail text", now)
    assert path.parent == tmp_path / "infra" / "telegram" / "queue"
    event = json.loads(path.read_text())
    assert event == {
        "schema_version": "1.0.0",
        "id": event["id"],
        "source_agent": "health-check",
        "severity": "critical",
        "kind": "engine_stalled",
        "payload": {"text": "detail text"},
        "requires_reply": False,
        "ts": "2026-07-20T12:00:00Z",
    }
    assert event["id"].startswith("evt-health-engine-stalled-")


def test_run_alerts_and_queues_event_when_alpaca_unreachable(tmp_path, monkeypatch):
    now = dt.datetime(2026, 7, 20, 12, 0, 0, tzinfo=dt.timezone.utc)
    write_heartbeat(tmp_path, now - dt.timedelta(minutes=1))  # fresh — not the failure mode here
    monkeypatch.setattr(hc, "check_alpaca_connectivity", lambda: (False, "connection failed: boom"))

    rc = hc.run(tmp_path, now=now)

    assert rc == 1
    queued = list((tmp_path / "infra/telegram/queue").glob("*.json"))
    assert len(queued) == 1
    event = json.loads(queued[0].read_text())
    assert event["kind"] == "alpaca_disconnected"
    assert event["severity"] == "critical"


def test_run_alerts_and_queues_event_when_heartbeat_stale(tmp_path, monkeypatch):
    now = dt.datetime(2026, 7, 20, 12, 0, 0, tzinfo=dt.timezone.utc)
    write_heartbeat(tmp_path, now - dt.timedelta(minutes=30))
    monkeypatch.setattr(hc, "check_alpaca_connectivity", lambda: (True, "ok"))

    rc = hc.run(tmp_path, now=now)

    assert rc == 1
    queued = list((tmp_path / "infra/telegram/queue").glob("*.json"))
    assert len(queued) == 1
    event = json.loads(queued[0].read_text())
    assert event["kind"] == "engine_stalled"
    assert event["severity"] == "critical"


def test_run_is_quiet_and_healthy_when_both_checks_pass(tmp_path, monkeypatch):
    now = dt.datetime(2026, 7, 20, 12, 0, 0, tzinfo=dt.timezone.utc)
    write_heartbeat(tmp_path, now - dt.timedelta(seconds=30))
    monkeypatch.setattr(hc, "check_alpaca_connectivity", lambda: (True, "ok"))

    rc = hc.run(tmp_path, now=now)

    assert rc == 0
    assert list((tmp_path / "infra/telegram/queue").glob("*.json")) == []


def test_find_repo_root_walks_up(tmp_path):
    (tmp_path / "contracts").mkdir()
    (tmp_path / "CLAUDE.md").write_text("x")
    nested = tmp_path / "a" / "b" / "c"
    nested.mkdir(parents=True)
    assert hc.find_repo_root(nested) == tmp_path
