"""P6 logic tests: owner pinning, two-step live approval, rejection,
kill switch, queue classification, task filing — no bot token needed."""

import json
from pathlib import Path

import pytest

from telegram_bridge import core


@pytest.fixture()
def root(tmp_path: Path, monkeypatch) -> Path:
    (tmp_path / "contracts").mkdir()
    (tmp_path / "CLAUDE.md").write_text("test root")
    monkeypatch.setenv("TELEGRAM_OWNER_ID", "777000111")
    return tmp_path


def seed_promotion(root: Path, to_stage: str = "live") -> str:
    promo_id = f"promo-test-{to_stage}"
    core.promotions_dir(root).mkdir(parents=True, exist_ok=True)
    record = {
        "schema_version": "1.0.0",
        "id": promo_id,
        "strategy_id": "sma-cross-test-v1",
        "from_stage": "paper",
        "to_stage": to_stage,
        "evidence": ["data/results/sma-cross-test-v1/paper_result.json"],
        "rationale": "test",
        "issued_at": "2026-07-19T19:00:00Z",
        "human_approval": {
            "required": to_stage == "live",
            "telegram_msg_id": None,
            "confirmation_msg_id": None,
            "approved_at": None,
        },
    }
    (core.promotions_dir(root) / f"{promo_id}.json").write_text(json.dumps(record))
    return promo_id


def test_owner_pinning(root):
    assert core.is_owner(777000111)
    assert not core.is_owner(123456)
    assert not core.is_owner(None)


def test_live_approval_requires_exact_confirm(root):
    promo_id = seed_promotion(root, "live")
    text, pending = core.start_approval(root, promo_id, approve_msg_id=1024)
    assert pending is not None and "CONFIRM" in text

    # Wrong reply cancels and does NOT write the approval.
    msg = core.confirm_approval(root, pending, "yes go ahead", confirm_msg_id=1030)
    assert "Cancelled" in msg
    assert core.load_promotion(root, promo_id)["human_approval"]["approved_at"] is None

    # Exact reply approves with both message ids recorded.
    text, pending = core.start_approval(root, promo_id, approve_msg_id=1024)
    msg = core.confirm_approval(root, pending, f"CONFIRM {promo_id}", confirm_msg_id=1031)
    assert "approved" in msg
    approval = core.load_promotion(root, promo_id)["human_approval"]
    assert approval == {
        "required": True,
        "telegram_msg_id": 1024,
        "confirmation_msg_id": 1031,
        "approved_at": approval["approved_at"],
    }
    assert approval["approved_at"] is not None


def test_non_live_approval_is_single_step(root):
    promo_id = seed_promotion(root, "paper")
    text, pending = core.start_approval(root, promo_id, approve_msg_id=55)
    assert pending is None and "Approved" in text
    assert core.load_promotion(root, promo_id)["human_approval"]["approved_at"] is not None


def test_reject_moves_record(root):
    promo_id = seed_promotion(root)
    core.reject_promotion(root, promo_id)
    assert not (core.promotions_dir(root) / f"{promo_id}.json").exists()
    assert (core.promotions_dir(root) / "rejected" / f"{promo_id}.json").exists()
    with pytest.raises(core.ApprovalError):
        core.load_promotion(root, promo_id)


def test_kill_switch_roundtrip(root):
    assert not core.kill_path(root).exists()
    core.halt(root, "test")
    assert core.kill_path(root).exists()
    assert core.resume(root) is True
    assert core.resume(root) is False


def test_queue_classification_and_mark_sent(root):
    qdir = core.queue_dir(root)
    qdir.mkdir(parents=True)
    for i, sev in enumerate(["info", "high", "warning", "critical"]):
        (qdir / f"evt-{i}.json").write_text(
            json.dumps(
                {
                    "schema_version": "1.0.0",
                    "id": f"evt-{i}",
                    "source_agent": "test",
                    "severity": sev,
                    "kind": "test_event",
                    "payload": {"text": f"event {i}"},
                    "requires_reply": False,
                    "ts": "2026-07-19T19:00:00Z",
                }
            )
        )
    immediate, batchable = core.scan_queue(root)
    assert [e["severity"] for e in immediate] == ["high", "critical"]
    assert [e["severity"] for e in batchable] == ["info", "warning"]

    core.mark_sent(immediate[0])
    immediate2, _ = core.scan_queue(root)
    assert [e["severity"] for e in immediate2] == ["critical"]
    assert (qdir / "sent" / "evt-1.json").exists()

    digest = core.format_digest(batchable)
    assert "event 0" in digest and "event 2" in digest


def test_free_text_files_task(root):
    path = core.file_task(root, "research gold miners", msg_id=99)
    task = json.loads(path.read_text())
    assert task["text"] == "research gold miners"
    assert task["telegram_msg_id"] == 99


def test_status_reports_kill_and_pending(root):
    seed_promotion(root)
    core.halt(root, "test")
    status = core.status_text(root)
    assert "ACTIVE" in status and "promo-test-live" in status
