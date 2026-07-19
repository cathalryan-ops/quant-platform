"""P7 acceptance: promotes/demotes correctly from seeded results and blocks
a live promotion until a complete two-step Telegram approval exists."""

import json
import shutil
from pathlib import Path

import pytest

import ranker
from backtest.data import content_hash

REPO_ROOT = Path(__file__).resolve().parents[3]

PAGE = """---
type: strategy
created: 2026-07-19
---

# Test Strategy

## Manifest

```strategy_manifest
{manifest}
```

## Lifecycle history

- 2026-07-19 — research — created
"""


@pytest.fixture()
def root(tmp_path: Path) -> Path:
    (tmp_path / "CLAUDE.md").write_text("test root")
    (tmp_path / "contracts").mkdir()
    shutil.copy(
        REPO_ROOT / "contracts/promotion_thresholds.toml",
        tmp_path / "contracts/promotion_thresholds.toml",
    )
    (tmp_path / "brain/wiki/strategies").mkdir(parents=True)
    return tmp_path


def seed_page(root: Path, lifecycle: str, strategy_id: str = "test-strat-v1") -> Path:
    manifest = {
        "schema_version": "1.0.0",
        "id": strategy_id,
        "wiki_page": f"brain/wiki/strategies/{strategy_id}.md",
        "market": "us_equities",
        "family": "swing",
        "universe": ["SPY"],
        "hypothesis": "test hypothesis",
        "signal_spec": {"language": "python", "entrypoint": "strategies/test_strat.py:Signal"},
        "risk": {"max_position_pct": 5.0, "stop_loss_pct": 2.0},
        "lifecycle": lifecycle,
        "scorecard": {
            "sharpe_wf": None,
            "sortino_wf": None,
            "max_drawdown_bt": None,
            "sharpe_paper": None,
            "max_drawdown_paper": None,
            "pnl_live": None,
            "rank": None,
        },
    }
    page = root / f"brain/wiki/strategies/{strategy_id}.md"
    page.write_text(PAGE.format(manifest=json.dumps(manifest, indent=2)))
    return page


def seed_snapshot(root: Path) -> tuple[str, str]:
    data = root / "data/snap.parquet"
    data.parent.mkdir(parents=True, exist_ok=True)
    data.write_bytes(b"parquet-stand-in")
    return "data/snap.parquet", content_hash(data)


def seed_backtest_result(root: Path, passed: bool, sharpe: float = 1.4) -> None:
    parquet_path, digest = seed_snapshot(root)
    out = root / "data/results/test-strat-v1"
    out.mkdir(parents=True, exist_ok=True)
    (out / "backtest_result.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "strategy_id": "test-strat-v1",
                "period": {"start": "2020-01-01", "end": "2023-12-29"},
                "metrics": {
                    "sharpe": sharpe,
                    "sortino": 1.6,
                    "max_drawdown_pct": 8.0,
                    "turnover": 3.0,
                },
                "slippage": {"model": "fixed_bps", "bps": 5.0},
                "equity_curve_path": "x.png",
                "data_snapshot": {
                    "parquet_path": parquet_path,
                    "content_hash": digest,
                    "source_feed": "synthetic_test",
                    "period": {"start": "2020-01-01", "end": "2023-12-29"},
                },
                "passed_thresholds": passed,
                "notes": "seeded",
                "generated_at": "2026-07-19T18:00:00Z",
            }
        )
    )


def seed_paper_result(root: Path, passed: bool) -> None:
    parquet_path, digest = seed_snapshot(root)
    out = root / "data/results/test-strat-v1"
    out.mkdir(parents=True, exist_ok=True)
    (out / "paper_result.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "strategy_id": "test-strat-v1",
                "period": {"start": "2026-06-01", "end": "2026-06-30"},
                "metrics": {
                    "sharpe": 1.1,
                    "sortino": 1.3,
                    "max_drawdown_pct": 3.0,
                    "pnl_usd": 500.0,
                    "num_trades": 12,
                },
                "slippage": {"model": "quote_close_plus_bps", "bps": 3.0},
                "equity_curve_path": "x.csv",
                "data_snapshot": {
                    "parquet_path": parquet_path,
                    "content_hash": digest,
                    "source_feed": "synthetic_test",
                    "period": {"start": "2020-01-01", "end": "2023-12-29"},
                },
                "passed_thresholds": passed,
                "notes": "seeded",
                "generated_at": "2026-06-30T21:00:00Z",
            }
        )
    )


def lifecycle_of(page: Path) -> str:
    return ranker.read_manifest(page).lifecycle


def test_research_promotes_when_implementation_exists(root):
    page = seed_page(root, "research")
    impl = root / "sandbox/backtest/strategies/test_strat.py"
    impl.parent.mkdir(parents=True)
    impl.write_text("class Signal: ...")
    ranker.run_ranker(root)
    assert lifecycle_of(page) == "backtest"


def test_backtest_pass_promotes_to_paper_and_updates_scorecard(root):
    page = seed_page(root, "backtest")
    seed_backtest_result(root, passed=True)
    report = ranker.run_ranker(root)
    m = ranker.read_manifest(page)
    assert m.lifecycle == "paper"
    assert m.scorecard.sharpe_wf == 1.4 and m.scorecard.rank == 1
    assert "backtest -> paper" in report.transitions[0]
    assert list((root / "data/promotions").glob("*paper.json"))


def test_backtest_fail_retires(root):
    page = seed_page(root, "backtest")
    seed_backtest_result(root, passed=False, sharpe=0.2)
    ranker.run_ranker(root)
    assert lifecycle_of(page) == "retired"


def test_live_promotion_blocks_until_two_step_approval(root):
    page = seed_page(root, "paper")
    seed_paper_result(root, passed=True)

    report = ranker.run_ranker(root)
    assert lifecycle_of(page) == "paper", "must NOT go live without approval"
    assert report.pending_live == ["test-strat-v1"]
    promo_files = list((root / "data/promotions").glob("*live.json"))
    assert len(promo_files) == 1
    event = json.loads(
        next((root / "infra/telegram/queue").glob("evt-*live.json")).read_text()
    )
    assert event["severity"] == "high" and event["requires_reply"] is True

    # Second run without approval: still blocked, no duplicate records.
    ranker.run_ranker(root)
    assert lifecycle_of(page) == "paper"
    assert len(list((root / "data/promotions").glob("*live.json"))) == 1

    # Complete the two-step approval (as the bridge would) and re-run.
    promo = json.loads(promo_files[0].read_text())
    promo["human_approval"] = {
        "required": True,
        "telegram_msg_id": 1024,
        "confirmation_msg_id": 1031,
        "approved_at": "2026-07-19T19:05:00Z",
    }
    promo_files[0].write_text(json.dumps(promo))
    report = ranker.run_ranker(root)
    assert lifecycle_of(page) == "live"
    assert any("paper -> live (approved)" in t for t in report.transitions)


def test_tampered_snapshot_result_is_ignored(root):
    page = seed_page(root, "backtest")
    seed_backtest_result(root, passed=True)
    (root / "data/snap.parquet").write_bytes(b"tampered")
    report = ranker.run_ranker(root)
    assert lifecycle_of(page) == "backtest", "tampered evidence must not promote"
    assert report.ignored_results
