"""Stdlib-only tests for infra/dashboard/generate.py.

Run with:
    python3 -m unittest infra/dashboard/test_generate.py -v
or:
    python3 infra/dashboard/test_generate.py
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent))

import generate  # noqa: E402


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _strategy_page(strategy_id: str, family: str, lifecycle: str, scorecard: dict) -> str:
    manifest = {
        "schema_version": "1.0.0",
        "id": strategy_id,
        "wiki_page": f"brain/wiki/strategies/{strategy_id}.md",
        "market": "us_equities",
        "family": family,
        "universe": ["SPY"],
        "hypothesis": "test hypothesis",
        "signal_spec": {"language": "python", "entrypoint": f"strategies/{strategy_id}.py:Signal"},
        "risk": {"max_position_pct": 5.0, "stop_loss_pct": 2.0},
        "lifecycle": lifecycle,
        "scorecard": scorecard,
    }
    body = json.dumps(manifest, indent=2)
    return f"""---
type: strategy
created: 2026-07-19
---

# {strategy_id}

## Manifest

```strategy_manifest
{body}
```
"""


def _empty_scorecard(**overrides) -> dict:
    base = {
        "sharpe_wf": None,
        "sortino_wf": None,
        "max_drawdown_bt": None,
        "sharpe_paper": None,
        "max_drawdown_paper": None,
        "pnl_live": None,
        "rank": None,
    }
    base.update(overrides)
    return base


def _promotion(promo_id: str, strategy_id: str, from_stage: str, to_stage: str, complete: bool) -> dict:
    approval = (
        {"required": True, "telegram_msg_id": 10, "confirmation_msg_id": 11, "approved_at": "2026-07-19T19:05:00Z"}
        if complete
        else {"required": True, "telegram_msg_id": None, "confirmation_msg_id": None, "approved_at": None}
    )
    return {
        "schema_version": "1.0.0",
        "id": promo_id,
        "strategy_id": strategy_id,
        "from_stage": from_stage,
        "to_stage": to_stage,
        "evidence": [],
        "rationale": "test rationale",
        "issued_at": "2026-07-19T19:00:00Z",
        "human_approval": approval,
    }


def _event(event_id: str, severity: str, kind: str = "daily_digest") -> dict:
    return {
        "schema_version": "1.0.0",
        "id": event_id,
        "source_agent": "test-agent",
        "severity": severity,
        "kind": kind,
        "payload": {},
        "requires_reply": False,
        "ts": "2026-07-19T20:00:00Z",
    }


def _make_base_repo(root: Path) -> None:
    _write(root / "CLAUDE.md", "# fake constitution\n")
    (root / "contracts").mkdir(parents=True, exist_ok=True)
    _write(root / "contracts" / "strategy_manifest.schema.json", "{}")


class TestSyntheticRepo(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TemporaryDirectory()
        self.root = Path(self.tmp.name)
        _make_base_repo(self.root)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_strategies_parsed_and_rank_ordered(self) -> None:
        _write(
            self.root / "brain/wiki/strategies/alpha-strat.md",
            _strategy_page("alpha-strat", "ms_shift", "live", _empty_scorecard(rank=2, sharpe_wf=1.2)),
        )
        _write(
            self.root / "brain/wiki/strategies/beta-strat.md",
            _strategy_page("beta-strat", "swing", "research", _empty_scorecard(rank=1)),
        )
        _write(
            self.root / "brain/wiki/strategies/gamma-strat.md",
            _strategy_page("gamma-strat", "swing", "retired", _empty_scorecard(rank=None)),
        )

        html_out = generate.render(self.root)

        self.assertIn("alpha-strat", html_out)
        self.assertIn("beta-strat", html_out)
        self.assertIn("gamma-strat", html_out)
        self.assertIn("lifecycle-live", html_out)
        self.assertIn("lifecycle-research", html_out)
        self.assertIn("lifecycle-retired", html_out)

        # rank ordering: beta (rank=1) before alpha (rank=2) before gamma (null, last)
        idx_beta = html_out.index("beta-strat")
        idx_alpha = html_out.index("alpha-strat")
        idx_gamma = html_out.index("gamma-strat")
        self.assertLess(idx_beta, idx_alpha)
        self.assertLess(idx_alpha, idx_gamma)

        # null scorecard fields render as em-dash
        self.assertIn("&mdash;", html_out)

    def test_kill_switch_present_and_absent(self) -> None:
        html_present = generate.render(self.root)
        self.assertIn("clear", html_present.lower())
        self.assertNotIn("KILL SWITCH ENGAGED", html_present)

        _write(self.root / "KILL", "")
        html_kill = generate.render(self.root)
        self.assertIn("KILL SWITCH ENGAGED", html_kill)

    def test_budget_freeze_present_and_absent(self) -> None:
        html_clear = generate.render(self.root)
        self.assertNotIn("BUDGET FROZEN", html_clear)

        _write(self.root / "infra/paperclip/FROZEN", "")
        html_frozen = generate.render(self.root)
        self.assertIn("BUDGET FROZEN", html_frozen)

    def test_promotion_approval_status_distinguished(self) -> None:
        _write(
            self.root / "data/promotions/promo-incomplete.json",
            json.dumps(_promotion("promo-incomplete", "alpha-strat", "paper", "live", complete=False)),
        )
        _write(
            self.root / "data/promotions/promo-complete.json",
            json.dumps(_promotion("promo-complete", "beta-strat", "backtest", "paper", complete=True)),
        )

        html_out = generate.render(self.root)

        self.assertIn("AWAITING APPROVAL", html_out)
        self.assertIn("approved", html_out)
        # the incomplete-to-live promotion should get the distinct highlight class
        self.assertIn("row-live-pending", html_out)

    def test_rejected_promotions_listed_separately(self) -> None:
        _write(
            self.root / "data/promotions/promo-active.json",
            json.dumps(_promotion("promo-active", "alpha-strat", "paper", "live", complete=True)),
        )
        _write(
            self.root / "data/promotions/rejected/promo-old.json",
            json.dumps(_promotion("promo-old", "gamma-strat", "research", "backtest", complete=True)),
        )

        html_out = generate.render(self.root)
        self.assertIn("promo-active", html_out)
        self.assertIn("Rejected promotions", html_out)
        self.assertIn("promo-old", html_out)

    def test_queue_depth_and_severity(self) -> None:
        _write(self.root / "infra/telegram/queue/evt-1.json", json.dumps(_event("evt-1", "info")))
        _write(self.root / "infra/telegram/queue/evt-2.json", json.dumps(_event("evt-2", "critical")))
        _write(self.root / "infra/telegram/queue/sent/evt-3.json", json.dumps(_event("evt-3", "info")))

        html_out = generate.render(self.root)
        self.assertIn("Total pending: <strong>2</strong>", html_out)
        self.assertIn("critical: 1", html_out)
        self.assertIn("info: 1", html_out)
        # sent/ events must not be counted
        self.assertNotIn("Total pending: <strong>3</strong>", html_out)

    def test_postmortems_listed(self) -> None:
        _write(
            self.root / "brain/wiki/postmortems/some-postmortem.md",
            "# Some Postmortem Title\n\nBody text.\n",
        )
        html_out = generate.render(self.root)
        self.assertIn("Some Postmortem Title", html_out)

    def test_find_repo_root_walks_up(self) -> None:
        nested = self.root / "infra" / "dashboard"
        nested.mkdir(parents=True, exist_ok=True)
        found = generate.find_repo_root(nested)
        self.assertEqual(found, self.root)


class TestEmptyRepo(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TemporaryDirectory()
        self.root = Path(self.tmp.name)
        _make_base_repo(self.root)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_renders_without_raising_and_looks_like_html(self) -> None:
        html_out = generate.render(self.root)
        self.assertIn("<html", html_out)
        self.assertIn("<body", html_out)
        self.assertIn("</html>", html_out)
        self.assertIn("yet", html_out.lower())

    def test_none_yet_messaging_for_each_section(self) -> None:
        html_out = generate.render(self.root)
        self.assertIn("No strategies yet", html_out)
        self.assertIn("No pending promotions", html_out)
        self.assertIn("Queue empty", html_out)
        self.assertIn("No postmortems yet", html_out)

    def test_data_dir_missing_entirely_is_fine(self) -> None:
        # data/ is gitignored and frequently absent entirely in a fresh
        # checkout; confirm that's handled the same as an empty directory.
        self.assertFalse((self.root / "data").exists())
        html_out = generate.render(self.root)
        self.assertIn("No pending promotions", html_out)


class TestRealRepo(unittest.TestCase):
    def test_runs_against_actual_repo_without_crashing(self) -> None:
        real_root = generate.find_repo_root(Path(__file__).resolve().parent)
        html_out = generate.render(real_root)
        self.assertIn("<html", html_out)
        self.assertIn("Quant Platform", html_out)
        # sanity: known seeded strategy ids should show up
        self.assertIn("ms-shift-spy-v1", html_out)
        self.assertIn("sma-cross-demo", html_out)


if __name__ == "__main__":
    unittest.main()
