"""P7 — Ranker & promotion pipeline (deterministic mechanics).

Reads every strategy page's manifest block + result files, applies
contracts/promotion_thresholds.toml, and drives the lifecycle state machine:

  research -> backtest   auto, once the signal implementation exists
  backtest -> paper      auto if backtest passed_thresholds
  paper    -> live       NEVER direct: issues a promotion record in
                         data/promotions/ + a high-severity Telegram event;
                         the transition applies only once human_approval is
                         complete (two-step, via the bridge)
  any      -> retired    failed thresholds (demote aggressively)

Every transition rewrites the wiki manifest (lifecycle + scorecard), appends
a dated rationale to the page's Lifecycle history, and re-ranks by
walk-forward Sharpe. Results whose pinned snapshot hash no longer matches
the parquet on disk are ignored (reproducibility rule).
"""

from __future__ import annotations

import datetime as dt
import json
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from backtest.data import content_hash
from contracts import BacktestResult, PaperResult, Promotion, StrategyManifest

MANIFEST_RE = re.compile(r"(```strategy_manifest\n)(.*?)(```)", re.S)


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class RankerReport:
    transitions: list[str] = field(default_factory=list)
    pending_live: list[str] = field(default_factory=list)
    ignored_results: list[str] = field(default_factory=list)


def load_thresholds(repo_root: Path) -> dict:
    with open(repo_root / "contracts/promotion_thresholds.toml", "rb") as f:
        return tomllib.load(f)


def strategy_pages(repo_root: Path) -> list[Path]:
    return sorted((repo_root / "brain/wiki/strategies").glob("*.md"))


def read_manifest(page: Path) -> StrategyManifest | None:
    m = MANIFEST_RE.search(page.read_text())
    if not m:
        return None
    return StrategyManifest.model_validate(json.loads(m.group(2)))


def write_manifest(page: Path, manifest: StrategyManifest, rationale: str) -> None:
    text = page.read_text()
    block = json.dumps(json.loads(manifest.model_dump_json()), indent=2)
    text = MANIFEST_RE.sub(lambda m: m.group(1) + block + "\n" + m.group(3), text, count=1)
    entry = f"- {now_utc()[:10]} — {manifest.lifecycle} — {rationale}\n"
    if "## Lifecycle history" in text:
        text = text.rstrip("\n") + "\n" + entry
    else:
        text += f"\n## Lifecycle history\n\n{entry}"
    page.write_text(text)


def _valid_result(repo_root: Path, raw: dict, path: Path, report: RankerReport) -> bool:
    """Reject results whose pinned snapshot hash no longer matches disk."""
    snap = raw["data_snapshot"]
    parquet = repo_root / snap["parquet_path"]
    if parquet.exists() and content_hash(parquet) != snap["content_hash"]:
        report.ignored_results.append(str(path))
        return False
    return True


def _emit(repo_root: Path, promotion: Promotion, severity: str) -> None:
    """Write the promotion record + its Telegram event."""
    pdir = repo_root / "data/promotions"
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / f"{promotion.id}.json").write_text(promotion.model_dump_json(indent=2) + "\n")
    qdir = repo_root / "infra/telegram/queue"
    qdir.mkdir(parents=True, exist_ok=True)
    event = {
        "schema_version": "1.0.0",
        "id": f"evt-{promotion.id}",
        "source_agent": "ranker",
        "severity": severity,
        "kind": "promotion_request",
        "payload": {
            "promotion_id": promotion.id,
            "strategy_id": promotion.strategy_id,
            "to_stage": promotion.to_stage,
            "text": f"{promotion.strategy_id}: {promotion.from_stage} -> "
            f"{promotion.to_stage}. {promotion.rationale}",
        },
        "requires_reply": promotion.to_stage == "live",
        "ts": now_utc(),
    }
    (qdir / f"evt-{promotion.id}.json").write_text(json.dumps(event, indent=2) + "\n")


def _promotion(manifest: StrategyManifest, to_stage: str, evidence: list[str], rationale: str) -> Promotion:
    return Promotion.model_validate(
        {
            "schema_version": "1.0.0",
            "id": f"promo-{now_utc()[:10]}-{manifest.id}-{to_stage}",
            "strategy_id": manifest.id,
            "from_stage": manifest.lifecycle,
            "to_stage": to_stage,
            "evidence": evidence,
            "rationale": rationale,
            "issued_at": now_utc(),
            "human_approval": {
                "required": to_stage == "live",
                "telegram_msg_id": None,
                "confirmation_msg_id": None,
                "approved_at": None,
            },
        }
    )


def run_ranker(repo_root: Path) -> RankerReport:
    report = RankerReport()
    thresholds = load_thresholds(repo_root)
    ranked: list[tuple[float, Path, StrategyManifest]] = []

    for page in strategy_pages(repo_root):
        manifest = read_manifest(page)
        if manifest is None:
            continue
        results_dir = repo_root / "data/results" / manifest.id
        transition = _advance(repo_root, page, manifest, results_dir, thresholds, report)
        if transition:
            report.transitions.append(transition)
        if manifest.scorecard.sharpe_wf is not None:
            ranked.append((manifest.scorecard.sharpe_wf, page, manifest))

    # Rank survivors by walk-forward Sharpe (1 = best).
    ranked.sort(key=lambda t: -t[0])
    for i, (_, page, manifest) in enumerate(ranked, start=1):
        if manifest.scorecard.rank != i:
            manifest.scorecard.rank = i
            write_manifest(page, manifest, f"rank updated to {i} (walk-forward Sharpe ordering)")
    return report


def _advance(
    repo_root: Path,
    page: Path,
    manifest: StrategyManifest,
    results_dir: Path,
    thresholds: dict,
    report: RankerReport,
) -> str | None:
    stage = manifest.lifecycle

    if stage == "research":
        impl = repo_root / "sandbox/backtest" / manifest.signal_spec.entrypoint.split(":")[0]
        if impl.exists():
            manifest.lifecycle = "backtest"
            rationale = f"signal implementation {impl.name} exists; auto-promoted to backtest"
            write_manifest(page, manifest, rationale)
            _emit(repo_root, _promotion(manifest, "backtest", [], rationale), "info")
            return f"{manifest.id}: research -> backtest"
        return None

    if stage == "backtest":
        result_path = results_dir / "backtest_result.json"
        if not result_path.exists():
            return None
        raw = json.loads(result_path.read_text())
        if not _valid_result(repo_root, raw, result_path, report):
            return None
        result = BacktestResult.model_validate(raw)
        manifest.scorecard.sharpe_wf = result.metrics.sharpe
        manifest.scorecard.sortino_wf = result.metrics.sortino
        manifest.scorecard.max_drawdown_bt = result.metrics.max_drawdown_pct
        evidence = [str(result_path.relative_to(repo_root))]
        if result.passed_thresholds:
            manifest.lifecycle = "paper"
            rationale = (
                f"backtest passed thresholds (Sharpe {result.metrics.sharpe}, "
                f"Sortino {result.metrics.sortino}, maxDD {result.metrics.max_drawdown_pct}%)"
            )
            write_manifest(page, manifest, rationale)
            _emit(repo_root, _promotion(manifest, "paper", evidence, rationale), "info")
            return f"{manifest.id}: backtest -> paper"
        manifest.lifecycle = "retired"
        rationale = (
            f"backtest failed thresholds (Sharpe {result.metrics.sharpe} vs min "
            f"{thresholds['backtest_to_paper']['min_walkforward_sharpe']}); retired"
        )
        write_manifest(page, manifest, rationale)
        _emit(repo_root, _promotion(manifest, "retired", evidence, rationale), "warning")
        return f"{manifest.id}: backtest -> retired"

    if stage == "paper":
        result_path = results_dir / "paper_result.json"
        if not result_path.exists():
            return None
        raw = json.loads(result_path.read_text())
        if not _valid_result(repo_root, raw, result_path, report):
            return None
        result = PaperResult.model_validate(raw)
        manifest.scorecard.sharpe_paper = result.metrics.sharpe
        manifest.scorecard.max_drawdown_paper = result.metrics.max_drawdown_pct
        evidence = [str(result_path.relative_to(repo_root))]

        pending = repo_root / "data/promotions" / f"promo-{now_utc()[:10]}-{manifest.id}-live.json"
        if pending.exists():
            promo = json.loads(pending.read_text())
            approval = promo["human_approval"]
            if all(approval.get(k) is not None for k in ("telegram_msg_id", "confirmation_msg_id", "approved_at")):
                manifest.lifecycle = "live"
                rationale = f"two-step Telegram approval complete ({approval['approved_at']}); LIVE"
                write_manifest(page, manifest, rationale)
                return f"{manifest.id}: paper -> live (approved)"
            report.pending_live.append(manifest.id)
            write_manifest(page, manifest, "paper scorecard updated; live promotion awaiting approval")
            return None

        if result.passed_thresholds:
            rationale = (
                f"paper passed thresholds (Sharpe {result.metrics.sharpe}, maxDD "
                f"{result.metrics.max_drawdown_pct}%, {result.metrics.num_trades} trades); "
                f"requesting LIVE promotion — human approval required"
            )
            write_manifest(page, manifest, rationale)
            _emit(repo_root, _promotion(manifest, "live", evidence, rationale), "high")
            report.pending_live.append(manifest.id)
            return f"{manifest.id}: live promotion requested (blocked on approval)"
        manifest.lifecycle = "retired"
        rationale = f"paper failed thresholds (Sharpe {result.metrics.sharpe}); retired"
        write_manifest(page, manifest, rationale)
        _emit(repo_root, _promotion(manifest, "retired", evidence, rationale), "warning")
        return f"{manifest.id}: paper -> retired"

    return None


def main() -> int:
    from backtest.engine import find_repo_root

    report = run_ranker(find_repo_root(Path.cwd()))
    for line in report.transitions:
        print(line)
    if report.pending_live:
        print(f"awaiting approval: {', '.join(report.pending_live)}")
    if report.ignored_results:
        print(f"ignored (snapshot hash mismatch): {', '.join(report.ignored_results)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
