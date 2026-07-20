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


def _strategy_page(
    strategy_id: str,
    family: str,
    lifecycle: str,
    scorecard: dict,
    created: str = "2026-07-19",
    history_bullets: list[str] | None = None,
) -> str:
    """Build a synthetic wiki page.

    `history_bullets`, if given, is a list of pre-formatted markdown bullet
    blocks (each a full '- YYYY-MM-DD — ...' string, optionally with extra
    lines appended for continuation-line testing) rendered verbatim under
    a '## Lifecycle history' heading. Omit it to get a page with no
    Lifecycle history section at all (the empty-state case).
    """
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

    history_section = ""
    if history_bullets:
        history_section = "\n\n## Lifecycle history\n\n" + "\n".join(history_bullets) + "\n"

    return f"""---
type: strategy
created: {created}
---

# {strategy_id}

## Manifest

```strategy_manifest
{body}
```
{history_section}"""


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


def _lineage_section(html_out: str) -> str:
    """Slice out just the 'Strategy lineage' section.

    The flat, rank-sorted strategies table (a separate section, rendered
    earlier in the document) also contains every strategy id as link text —
    for null-ranked entries its order is a stable-sort artifact of
    alphabetical file-glob order, NOT the lineage/version ordering under
    test here. Any assertion about lineage ordering must search within this
    slice, not the whole document, or it can pass by coincidence (when the
    two orderings happen to agree) rather than actually testing lineage
    order.
    """
    start = html_out.index('id="strategy-lineage"')
    end = html_out.index('<section', start + 1)
    return html_out[start:end]


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

    def test_family_grouping_and_version_suffix_ordering(self) -> None:
        # v2 written to disk (and created) BEFORE v1, to prove ordering
        # comes from the '-vN' id suffix, not file order or creation date.
        _write(
            self.root / "brain/wiki/strategies/ms-shift-spy-v2.md",
            _strategy_page(
                "ms-shift-spy-v2", "ms_shift", "retired", _empty_scorecard(),
                created="2026-01-01",
            ),
        )
        _write(
            self.root / "brain/wiki/strategies/ms-shift-spy-v1.md",
            _strategy_page(
                "ms-shift-spy-v1", "ms_shift", "retired", _empty_scorecard(),
                created="2026-06-01",
            ),
        )
        _write(
            self.root / "brain/wiki/strategies/sma-cross-demo.md",
            _strategy_page("sma-cross-demo", "swing", "research", _empty_scorecard()),
        )

        html_out = generate.render(self.root)
        lineage = _lineage_section(html_out)

        self.assertIn("ms_shift", lineage)
        self.assertIn("swing", lineage)
        # v1 must appear before v2 in the lineage view despite the reversed
        # creation/file-write order.
        idx_v1 = lineage.index("ms-shift-spy-v1<")
        idx_v2 = lineage.index("ms-shift-spy-v2<")
        self.assertLess(idx_v1, idx_v2)
        # multi-member family gets a count suffix; single-member does not.
        self.assertIn("ms_shift &mdash; 2 strategies", lineage)
        self.assertNotIn("swing &mdash; 1 strategies", lineage)

    def test_lineage_ordering_falls_back_to_created_date_without_version_suffix(self) -> None:
        # Neither id has a '-vN' suffix, so ordering must fall back to the
        # frontmatter created: date — 'zeta' (created first) before 'alpha'
        # (created later), i.e. NOT alphabetical order.
        _write(
            self.root / "brain/wiki/strategies/zeta-strategy.md",
            _strategy_page(
                "zeta-strategy", "swing", "research", _empty_scorecard(),
                created="2026-01-01",
            ),
        )
        _write(
            self.root / "brain/wiki/strategies/alpha-strategy.md",
            _strategy_page(
                "alpha-strategy", "swing", "research", _empty_scorecard(),
                created="2026-06-01",
            ),
        )

        lineage = _lineage_section(generate.render(self.root))
        idx_zeta = lineage.index("zeta-strategy<")
        idx_alpha = lineage.index("alpha-strategy<")
        self.assertLess(
            idx_zeta, idx_alpha, "earlier created: date must sort first, not alphabetical id"
        )

    def test_lineage_ordering_falls_back_to_alphabetical_with_no_created_date(self) -> None:
        # Hand-write pages with no frontmatter at all (not even a created:
        # field) — the last-resort fallback tier.
        manifest_b = json.dumps(
            {
                "schema_version": "1.0.0", "id": "b-strategy",
                "wiki_page": "brain/wiki/strategies/b-strategy.md",
                "market": "us_equities", "family": "swing", "universe": ["SPY"],
                "hypothesis": "x",
                "signal_spec": {"language": "python", "entrypoint": "strategies/b.py:Signal"},
                "risk": {"max_position_pct": 5.0, "stop_loss_pct": 2.0},
                "lifecycle": "research", "scorecard": _empty_scorecard(),
            }
        )
        manifest_a = manifest_b.replace('"id": "b-strategy"', '"id": "a-strategy"').replace(
            "brain/wiki/strategies/b-strategy.md", "brain/wiki/strategies/a-strategy.md"
        )
        _write(
            self.root / "brain/wiki/strategies/b-strategy.md",
            f"# b-strategy\n\n```strategy_manifest\n{manifest_b}\n```\n",
        )
        _write(
            self.root / "brain/wiki/strategies/a-strategy.md",
            f"# a-strategy\n\n```strategy_manifest\n{manifest_a}\n```\n",
        )

        lineage = _lineage_section(generate.render(self.root))
        idx_a = lineage.index("a-strategy<")
        idx_b = lineage.index("b-strategy<")
        self.assertLess(idx_a, idx_b, "with no version suffix or created: date, falls back to alphabetical")

    def test_latest_lifecycle_history_bullet_shown_full_text_preserved_via_tooltip(self) -> None:
        long_bullet = "- 2026-07-20 — retired — " + ("x" * 250)
        _write(
            self.root / "brain/wiki/strategies/multi-history.md",
            _strategy_page(
                "multi-history", "ms_shift", "retired", _empty_scorecard(),
                history_bullets=[
                    "- 2026-07-01 — created at `research` — first entry, must NOT be shown",
                    "- 2026-07-10 — backtest — middle entry, must NOT be shown",
                    long_bullet,
                ],
            ),
        )
        html_out = generate.render(self.root)
        self.assertNotIn("first entry, must NOT be shown", html_out)
        self.assertNotIn("middle entry, must NOT be shown", html_out)
        # Truncated display text is present...
        self.assertIn("x" * 195, html_out)
        # ...and the FULL untruncated bullet is preserved somewhere (the
        # title="" tooltip), not silently dropped.
        self.assertIn("x" * 250, html_out)

    def test_short_history_bullet_has_no_redundant_tooltip(self) -> None:
        _write(
            self.root / "brain/wiki/strategies/short-history.md",
            _strategy_page(
                "short-history", "swing", "research", _empty_scorecard(),
                history_bullets=["- 2026-07-20 — created at `research` — short rationale"],
            ),
        )
        html_out = generate.render(self.root)
        self.assertIn("short rationale", html_out)
        self.assertNotIn('title="- 2026-07-20', html_out)

    def test_no_lifecycle_history_section_shows_placeholder(self) -> None:
        _write(
            self.root / "brain/wiki/strategies/no-history.md",
            _strategy_page("no-history", "swing", "research", _empty_scorecard(), history_bullets=None),
        )
        html_out = generate.render(self.root)
        self.assertIn("no Lifecycle history section", html_out)

    def test_raw_note_linking_substring_match_and_no_false_positive(self) -> None:
        _write(
            self.root / "brain/wiki/strategies/ms-shift-spy-v1.md",
            _strategy_page("ms-shift-spy-v1", "ms_shift", "retired", _empty_scorecard()),
        )
        _write(
            self.root / "brain/wiki/strategies/sma-cross-demo.md",
            _strategy_page("sma-cross-demo", "swing", "research", _empty_scorecard()),
        )
        _write(
            self.root / "brain/raw/ms-shift-spy-v1-fold-regime-hypothesis.md",
            "# fold regime hypothesis\n",
        )
        _write(self.root / "brain/raw/unrelated-note.md", "# unrelated\n")

        html_out = generate.render(self.root)
        self.assertIn("ms-shift-spy-v1-fold-regime-hypothesis", html_out)
        # sma-cross-demo has no matching raw note and no strategy id is a
        # substring of "unrelated-note" — must show the em-dash placeholder,
        # and the unrelated note must not be linked to either strategy.
        self.assertIn("&mdash;", html_out)
        self.assertNotIn("unrelated-note", html_out)

    def test_zero_raw_notes_is_handled_gracefully(self) -> None:
        # No brain/raw/ directory at all — must not crash, every strategy's
        # linked-notes column falls back to the em-dash placeholder.
        _write(
            self.root / "brain/wiki/strategies/solo-strategy.md",
            _strategy_page("solo-strategy", "ms_shift", "research", _empty_scorecard()),
        )
        self.assertFalse((self.root / "brain" / "raw").exists())
        html_out = generate.render(self.root)
        self.assertIn("solo-strategy", html_out)


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
