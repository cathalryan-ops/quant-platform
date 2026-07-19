"""P11 — Integration Test Conductor.

Runs ONE full loop on a toy strategy in a scratch copy of the repo layout:

  seed source -> strategy page (research) -> ranker: research->backtest
  -> backtest on a pinned trending snapshot (REAL thresholds) + ruleset
  export -> ranker: backtest->paper -> paper engine (Rust, sim feed)
  -> ranker: live promotion requested (blocked) -> two-step Telegram
  approval (the ONLY manual tap; simulated here via the bridge's own
  core functions) -> ranker: paper->live -> live engine dry loop (Rust,
  sim broker) incl. restart idempotency -> postmortem page + follow-up
  task (P9) -> seam report.

Scratch-root honesty: the ratified promotion_thresholds.toml applies
unchanged to the backtest gate; only [paper_to_live] is relaxed in the
scratch copy because a short synthetic paper run cannot establish a
Sharpe — that relaxation exists ONLY in the scratch dir, never in the repo.

Run:  cd sandbox/backtest && uv run python ../../scripts/integration_loop.py
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "sandbox/backtest"))
sys.path.insert(0, str(REPO / "infra/telegram"))

import contracts  # noqa: E402
import ranker  # noqa: E402
from backtest.data import content_hash, write_snapshot  # noqa: E402
from backtest.engine import run_backtest  # noqa: E402
from telegram_bridge import core as bridge  # noqa: E402

STRAT = "sma-cross-loop-v1"
SEAMS: list[str] = []


def seam(name: str, ok: bool, detail: str = "") -> None:
    SEAMS.append(f"{'OK  ' if ok else 'LEAK'} {name}{': ' + detail if detail else ''}")
    if not ok:
        print("\n".join(SEAMS))
        raise SystemExit(f"seam leaked: {name}")


def build_scratch() -> Path:
    scratch = Path(tempfile.mkdtemp(prefix="qp-loop-"))
    (scratch / "contracts").mkdir()
    (scratch / "live").mkdir()
    (scratch / "brain/wiki/strategies").mkdir(parents=True)
    (scratch / "brain/wiki/postmortems").mkdir(parents=True)
    (scratch / "brain/raw").mkdir(parents=True)
    (scratch / "sandbox/backtest/strategies").mkdir(parents=True)
    (scratch / "CLAUDE.md").write_text("scratch root (P11 integration loop)")
    shutil.copy(REPO / "live/guardrails.toml", scratch / "live/guardrails.toml")
    shutil.copy(REPO / "sandbox/backtest/strategies/sma_cross.py",
                scratch / "sandbox/backtest/strategies/sma_cross.py")
    thresholds = (REPO / "contracts/promotion_thresholds.toml").read_text()
    thresholds = re.sub(r"min_paper_sharpe = [\d.]+", "min_paper_sharpe = -99.0", thresholds)
    thresholds = re.sub(r"max_paper_drawdown_pct = [\d.]+", "max_paper_drawdown_pct = 100.0", thresholds)
    thresholds = re.sub(r"min_paper_days = \d+", "min_paper_days = 10", thresholds)
    (scratch / "contracts/promotion_thresholds.toml").write_text(thresholds)
    (scratch / "brain/index.md").write_text("# Brain Index\n\n## Strategies\n\n## Postmortems\n")
    (scratch / "brain/log.md").write_text("# Brain Log\n")
    return scratch


def seed_strategy_page(scratch: Path) -> Path:
    manifest = {
        "schema_version": "1.0.0", "id": STRAT,
        "wiki_page": f"brain/wiki/strategies/{STRAT}.md",
        "market": "us_equities", "family": "swing", "universe": ["SPY", "QQQ"],
        "hypothesis": "Toy: SMA(20/50) cross captures trend on trending data; killed if walk-forward Sharpe < 1.0 after costs.",
        "signal_spec": {"language": "python", "entrypoint": "strategies/sma_cross.py:Signal"},
        "risk": {"max_position_pct": 5.0, "stop_loss_pct": 2.0},
        "lifecycle": "research",
        "scorecard": {"sharpe_wf": None, "sortino_wf": None, "max_drawdown_bt": None,
                      "sharpe_paper": None, "max_drawdown_paper": None, "pnl_live": None, "rank": None},
    }
    (scratch / "brain/raw/toy-source.md").write_text("# Toy source\nSeeded for the loop.\n")
    page = scratch / f"brain/wiki/strategies/{STRAT}.md"
    page.write_text(
        "---\ntype: strategy\ncreated: 2026-07-19\n---\n\n# SMA Cross Loop\n\n"
        "## Manifest\n\n```strategy_manifest\n" + json.dumps(manifest, indent=2) + "\n```\n\n"
        "## Evidence\n\n## Lifecycle history\n\n- 2026-07-19 — research — seeded by P11\n"
    )
    return page


def make_trending_snapshot(scratch: Path) -> Path:
    rng = np.random.default_rng(7)
    dates = pd.bdate_range("2020-01-01", "2023-12-29").strftime("%Y-%m-%d")
    frames = []
    for i, sym in enumerate(["SPY", "QQQ"]):
        rets = rng.normal(0.0015, 0.006, len(dates))  # strong drift, mild noise
        close = 100.0 * (1 + i) * np.exp(np.cumsum(rets))
        frames.append(pd.DataFrame({
            "symbol": sym, "date": dates, "open": close * 0.999, "high": close * 1.005,
            "low": close * 0.995, "close": close, "volume": 1e6}))
    path = scratch / "data/us_equities/daily/loop.parquet"
    write_snapshot(pd.concat(frames, ignore_index=True), path)
    return path


def manifest_from_page(page: Path) -> contracts.StrategyManifest:
    return ranker.read_manifest(page)


def cargo(scratch: Path, *args: str) -> None:
    r = subprocess.run(["cargo", "run", "--quiet", "--manifest-path", str(REPO / "Cargo.toml"),
                        "-p", args[0], "--", *args[1:]],
                       cwd=scratch, capture_output=True, text=True,
                       env={**__import__("os").environ, "CARGO_TARGET_DIR": str(REPO / "target")})
    if r.returncode != 0:
        raise SystemExit(f"cargo {args} failed:\n{r.stderr[-2000:]}")


def main() -> None:
    scratch = build_scratch()
    print(f"scratch root: {scratch}")
    page = seed_strategy_page(scratch)
    seam("research proposal seeded", manifest_from_page(page).lifecycle == "research")

    ranker.run_ranker(scratch)
    seam("ranker: research -> backtest", manifest_from_page(page).lifecycle == "backtest")

    snapshot = make_trending_snapshot(scratch)
    pinned = content_hash(snapshot)
    result_path = run_backtest(
        manifest_from_page(page), start="2020-01-01", end="2023-12-29", repo_root=scratch,
        snapshot_path=snapshot, expected_hash=pinned, fetch=False, source_feed="synthetic_loop")
    bt = json.loads(result_path.read_text())
    seam("backtest passes REAL thresholds", bt["passed_thresholds"],
         f"Sharpe {bt['metrics']['sharpe']}")
    ruleset_path = result_path.parent / "ruleset.json"
    seam("ruleset exported (ADR 0002)", ruleset_path.exists())

    ranker.run_ranker(scratch)
    seam("ranker: backtest -> paper", manifest_from_page(page).lifecycle == "paper")

    manifest_file = scratch / "manifest.json"
    manifest_file.write_text(manifest_from_page(page).model_dump_json(indent=2))
    cargo(scratch, "paper-engine", "--manifest", str(manifest_file), "--ruleset", str(ruleset_path),
          "--feed", "sim", "--sessions", "120", "--out", str(scratch / "data/results"))
    paper = json.loads((scratch / f"data/results/{STRAT}/paper_result.json").read_text())
    seam("paper session emitted valid result with trades",
         paper["strategy_id"] == STRAT and paper["metrics"]["num_trades"] > 0,
         f"{paper['metrics']['num_trades']} trades")

    report = ranker.run_ranker(scratch)
    seam("live promotion requested + BLOCKED", STRAT in report.pending_live
         and manifest_from_page(page).lifecycle == "paper")
    promo_id = next((scratch / "data/promotions").glob(f"*{STRAT}-live.json")).stem
    event = next((scratch / "infra/telegram/queue").glob(f"evt-*{STRAT}-live.json"))
    seam("high-severity approval event queued", json.loads(event.read_text())["severity"] == "high")

    # THE manual tap, via the bridge's own two-step logic:
    text, pending = bridge.start_approval(scratch, promo_id, approve_msg_id=1024)
    seam("approve step 1 echoes + demands CONFIRM", pending is not None and "CONFIRM" in text)
    msg = bridge.confirm_approval(scratch, pending, f"CONFIRM {promo_id}", confirm_msg_id=1031)
    seam("approve step 2 records approval", "approved" in msg)

    ranker.run_ranker(scratch)
    seam("ranker: paper -> live (post-approval)", manifest_from_page(page).lifecycle == "live")

    manifest_file.write_text(manifest_from_page(page).model_dump_json(indent=2))
    cargo(scratch, "live", "--manifest", str(manifest_file), "--ruleset", str(ruleset_path),
          "--mode", "sim", "--sessions", "120")
    journal = scratch / f"data/live/{STRAT}/live_journal.jsonl"
    seam("live dry loop journaled fills", journal.exists() and journal.stat().st_size > 0)
    before = journal.read_text()
    cargo(scratch, "live", "--manifest", str(manifest_file), "--ruleset", str(ruleset_path),
          "--mode", "sim", "--sessions", "120")
    lines_before = [line for line in before.splitlines() if line]
    lines_after = [line for line in journal.read_text().splitlines() if line]
    seam("live restart is idempotent", lines_after == lines_before)

    # P9: postmortem + follow-up task (value backprop).
    pm = scratch / f"brain/wiki/postmortems/{STRAT}-paper-2030-01.md"
    pm.write_text(f"""---
type: postmortem
created: 2026-07-19
---

# {STRAT} — paper — {paper['period']['start']}..{paper['period']['end']}

## Expected vs realised

| Metric | Expected (backtest) | Realised (paper) | Delta |
|---|---|---|---|
| Sharpe | {bt['metrics']['sharpe']} | {paper['metrics']['sharpe']} | {round(paper['metrics']['sharpe'] - bt['metrics']['sharpe'], 3)} |
| Max drawdown % | {bt['metrics']['max_drawdown_pct']} | {paper['metrics']['max_drawdown_pct']} | {round(paper['metrics']['max_drawdown_pct'] - bt['metrics']['max_drawdown_pct'], 3)} |
| Slippage (bps) | {bt['slippage']['bps']} | {paper['slippage']['bps']} | {round(paper['slippage']['bps'] - bt['slippage']['bps'], 1)} |

## Verdict & follow-ups

Toy loop: realised edge on the sim feed differs from the trending fit as
expected. Follow-up filed: does the SMA cross degrade gracefully as drift
falls? Links: [[{STRAT}]], `data/results/{STRAT}/`.
""")
    bridge.file_task(scratch, f"P9 follow-up: quantify {STRAT} edge decay vs drift", msg_id=1)
    seam("postmortem written + follow-up task filed", pm.exists()
         and any((scratch / "infra/telegram/tasks").iterdir()))

    print("\n".join(SEAMS))
    print(f"\nFULL LOOP COMPLETE — only manual step was the two-step Telegram approval. Scratch: {scratch}")


if __name__ == "__main__":
    main()
