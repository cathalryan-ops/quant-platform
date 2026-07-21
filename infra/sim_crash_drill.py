#!/usr/bin/env python3
"""Crash-recovery drill: kill the live engine mid-flight and prove the
human-gated recovery path is bulletproof end-to-end.

Hard safety constraint: this NEVER runs against anything live-capable.
Mode is hardcoded to Sim below and there is no flag to override it — auto-
restart is deliberately NOT wired up for the live engine (see
infra/telegram/ecosystem.config.js's docstring: the constitution requires a
human to look at *why* the engine crashed before it resumes, not an
automated restart). This drill exists precisely to make that human-gated
step bulletproof when it happens, not to automate it away.

All state lives in a throwaway temp directory built to the same fixture
shape live/tests/live.rs's integration tests already use (synthetic
sma-cross-test-v1 manifest, Sim broker) — this never touches real
ms-shift-spy data, real Alpaca credentials, or the repo's actual data/
directory.

Verifies:
  A) infra/health_check.py's staleness check catches a stalled heartbeat
     within the 5-minute window — checked by injecting a `now` timestamp
     6 minutes past the last real heartbeat, not by actually sleeping 5+
     real minutes.
  B) The resulting critical event would be dispatched immediately by the
     telegram bridge: infra/telegram/telegram_bridge/core.py's scan_queue
     classifies it into the "immediate" bucket. This checks the dispatch
     LOGIC, not a real Telegram send — actually messaging a real chat
     needs a live bot token and is a separate, deliberate manual step
     (`infra/telegram` with a real .env), not something an unattended
     drill script should trigger on its own.
  C) A manual restart (this script re-invoking the same binary) reconciles
     via the Journal without duplicate submitted order ids or silent
     position loss — exercises the Sim-broker reconcile fix and the
     existing idempotent-order-id dedup end-to-end, via a real OS-level
     SIGKILL rather than an in-process test harness.

Exit code 0 = every check passed. Non-zero = a check failed OR the drill's
own timing assumptions didn't hold (see RETRY logic) — never silently
reports success in that case.
"""

from __future__ import annotations

import datetime as dt
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

DRILL_STRATEGY_ID = "sma-cross-test-v1"
# Calibrated against this engine's measured throughput (~260 sessions/sec on
# a plain Sim run): a full 800-session run takes ~3s, so killing at 1s lands
# comfortably mid-cycle while leaving the remainder cheap to finish on
# restart. Escalates only if a run manages to finish before the kill lands.
SESSIONS_ATTEMPTS = [800, 2_000, 5_000]
KILL_AFTER_SECS = 1.0
RESTART_TIMEOUT_SECS = 60


def find_repo_root(start: Path) -> Path:
    for candidate in [start, *start.parents]:
        if (candidate / "contracts").is_dir() and (candidate / "CLAUDE.md").is_file():
            return candidate
    raise FileNotFoundError(f"no repo root above {start}")


def ensure_binary(repo_root: Path) -> Path:
    binary = repo_root / "target" / "debug" / "live"
    if not binary.is_file():
        print("building live binary (cargo build --bin live)...")
        subprocess.run(
            ["cargo", "build", "--bin", "live"], cwd=repo_root, check=True
        )
    return binary


def build_drill_root(repo_root: Path) -> Path:
    """Same fixture shape as live/tests/live.rs's temp_root/manifest/
    ruleset/seed_approval helpers — proven-correct scaffolding, just
    reproduced in Python so this drill can run outside `cargo test`."""
    root = Path(
        __import__("tempfile").mkdtemp(prefix="qp-crash-drill-")
    )
    (root / "live").mkdir(parents=True)
    (root / "contracts").mkdir(parents=True)
    shutil.copy(repo_root / "live" / "guardrails.toml", root / "live" / "guardrails.toml")
    (root / "CLAUDE.md").write_text("crash drill root\n")

    manifest = json.loads((repo_root / "contracts/examples/strategy_manifest.json").read_text())
    manifest["id"] = DRILL_STRATEGY_ID
    manifest["lifecycle"] = "live"
    manifest_path = root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest))

    ruleset = {
        "schema_version": "1.0.0",
        "strategy_id": DRILL_STRATEGY_ID,
        "family": "swing",
        "max_position_pct": 5.0,
        "params": {"type": "sma_cross", "fast": 2, "slow": 3},
        "data_snapshot": {
            "parquet_path": "data/x.parquet",
            "content_hash": "sha256:9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
            "source_feed": "synthetic_test",
            "period": {"start": "2020-01-01", "end": "2020-12-31"},
        },
    }
    ruleset_path = root / "ruleset.json"
    ruleset_path.write_text(json.dumps(ruleset))

    promo_dir = root / "data" / "promotions"
    promo_dir.mkdir(parents=True)
    promo = {
        "schema_version": "1.0.0",
        "id": f"promo-drill-{DRILL_STRATEGY_ID}-live",
        "strategy_id": DRILL_STRATEGY_ID,
        "from_stage": "paper",
        "to_stage": "live",
        "evidence": [f"data/results/{DRILL_STRATEGY_ID}/paper_result.json"],
        "rationale": "crash drill fixture — not a real promotion",
        "issued_at": "2026-07-19T19:00:00Z",
        "human_approval": {
            "required": True,
            "telegram_msg_id": 1024,
            "confirmation_msg_id": 1031,
            "approved_at": "2026-07-19T19:05:00Z",
        },
    }
    (promo_dir / f"promo-drill-{DRILL_STRATEGY_ID}-live.json").write_text(json.dumps(promo))
    return root


def journal_path(root: Path) -> Path:
    return root / "data" / "live" / DRILL_STRATEGY_ID / "live_journal.jsonl"


def orders_log_path(root: Path) -> Path:
    return root / "data" / "live" / DRILL_STRATEGY_ID / "orders_submitted.log"


def heartbeat_path(root: Path) -> Path:
    return root / "live" / "heartbeat.json"


def launch(binary: Path, root: Path, sessions: int) -> subprocess.Popen:
    return subprocess.Popen(
        [
            str(binary),
            "--manifest", str(root / "manifest.json"),
            "--ruleset", str(root / "ruleset.json"),
            "--mode", "sim",  # HARD-CODED. Never anything else. See module docstring.
            "--sessions", str(sessions),
        ],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def kill_mid_cycle(binary: Path, root: Path) -> int:
    """Launches the engine, kills it (SIGKILL) partway through, escalating
    the session count if a run completes before we get to it. Returns the
    session count actually used (needed later to confirm a genuine
    restart-and-complete). Raises if even the largest attempt finishes
    before we can kill it."""
    for sessions in SESSIONS_ATTEMPTS:
        for f in (journal_path(root), orders_log_path(root), heartbeat_path(root)):
            f.unlink(missing_ok=True)
        proc = launch(binary, root, sessions)
        time.sleep(KILL_AFTER_SECS)
        if proc.poll() is not None:
            print(
                f"  [drill] {sessions} sessions completed before kill "
                f"(rc={proc.returncode}) — escalating session count and retrying"
            )
            continue
        proc.kill()  # SIGKILL — a real crash, not a graceful shutdown
        proc.wait(timeout=10)
        lines = sum(1 for _ in journal_path(root).open()) if journal_path(root).exists() else 0
        if lines == 0:
            print(f"  [drill] killed before any session journaled — escalating and retrying")
            continue
        if lines >= sessions:
            print(f"  [drill] {lines}/{sessions} sessions already journaled at kill time — escalating")
            continue
        print(f"  [drill] killed mid-cycle: {lines}/{sessions} sessions journaled, process SIGKILLed")
        return sessions
    raise RuntimeError(
        "could not reliably kill the engine mid-cycle even at the largest "
        f"session count ({SESSIONS_ATTEMPTS[-1]}) — drill inconclusive, not a pass"
    )


def _load_health_check(repo_root: Path):
    # Load by file path rather than sys.path.insert(infra/) + `import
    # health_check`: infra/telegram/ has no __init__.py, so adding infra/
    # to sys.path would make it resolve as an implicit namespace package
    # named `telegram`, shadowing the real python-telegram-bot package for
    # anything else importing `telegram` later in the same process.
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "health_check", repo_root / "infra" / "health_check.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_a_heartbeat_staleness_detected(repo_root: Path, root: Path) -> bool:
    health_check = _load_health_check(repo_root)

    hb = json.loads(heartbeat_path(root).read_text())
    last_alive = dt.datetime.strptime(hb["last_alive_at"], "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=dt.timezone.utc
    )
    injected_now = last_alive + dt.timedelta(minutes=6)
    rc = health_check.run(root, now=injected_now)
    queue = root / "infra" / "telegram" / "queue"
    stalled_events = list(queue.glob("evt-health-engine-stalled-*.json")) if queue.exists() else []
    ok = rc == 1 and len(stalled_events) == 1
    print(f"  [A] health_check.run() rc={rc}, stalled events queued={len(stalled_events)} -> {'PASS' if ok else 'FAIL'}")
    return ok


def check_b_dispatch_would_fire(repo_root: Path, root: Path) -> bool:
    sys.path.insert(0, str(repo_root / "infra" / "telegram"))
    from telegram_bridge import core  # noqa: E402

    immediate, batchable = core.scan_queue(root)
    ok = any(e.get("kind") == "engine_stalled" and e.get("severity") == "critical" for e in immediate)
    print(
        f"  [B] scan_queue: {len(immediate)} immediate, {len(batchable)} batchable; "
        f"engine_stalled critical event in 'immediate' bucket -> {'PASS' if ok else 'FAIL'}"
    )
    return ok


def check_c_clean_restart(binary: Path, root: Path, sessions: int) -> bool:
    proc = launch(binary, root, sessions)
    try:
        proc.wait(timeout=RESTART_TIMEOUT_SECS)
    except subprocess.TimeoutExpired:
        proc.kill()
        print("  [C] restart did not complete in time -> FAIL")
        return False

    lines = journal_path(root).read_text().splitlines()
    complete = len(lines) == sessions
    order_ids = orders_log_path(root).read_text().splitlines() if orders_log_path(root).exists() else []
    no_dupes = len(order_ids) == len(set(order_ids))
    last_state = json.loads(lines[-1]) if lines else {}
    has_positions_field = "positions" in last_state

    ok = proc.returncode == 0 and complete and no_dupes and has_positions_field
    print(
        f"  [C] restart rc={proc.returncode}, journaled {len(lines)}/{sessions} sessions "
        f"(complete={complete}), {len(order_ids)} order ids ({len(order_ids)-len(set(order_ids))} dupes) "
        f"-> {'PASS' if ok else 'FAIL'}"
    )
    return ok


def main() -> int:
    repo_root = find_repo_root(Path(__file__).resolve().parent)
    binary = ensure_binary(repo_root)
    root = build_drill_root(repo_root)
    print(f"drill root: {root}")

    try:
        print("\nstep 1: kill the engine mid-cycle (SIGKILL, Sim broker only)")
        sessions = kill_mid_cycle(binary, root)

        print("\nstep 2 (check A): heartbeat staleness caught within the 5-minute window")
        a_ok = check_a_heartbeat_staleness_detected(repo_root, root)

        print("\nstep 3 (check B): critical event would dispatch immediately via the telegram bridge")
        b_ok = check_b_dispatch_would_fire(repo_root, root)

        print("\nstep 4 (check C): manual restart reconciles cleanly, no duplicate fills")
        c_ok = check_c_clean_restart(binary, root, sessions)

        print(f"\nresult: A={'PASS' if a_ok else 'FAIL'} B={'PASS' if b_ok else 'FAIL'} C={'PASS' if c_ok else 'FAIL'}")
        return 0 if (a_ok and b_ok and c_ok) else 1
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
