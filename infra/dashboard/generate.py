#!/usr/bin/env python3
"""Local status dashboard generator.

Paperclip is the platform's intended dashboard, but per a deliberate scope
decision it is not installed in this environment (only its config was
hardened under infra/paperclip/). This script fills the resulting visibility
gap: it scans the repo's current on-disk state and renders a single
self-contained static HTML file with no server, no build step, and no
external dependencies (stdlib only).

Usage:
    python3 infra/dashboard/generate.py [--out PATH]

Output defaults to infra/dashboard/status.html (gitignored — it reflects
live, frequently-changing state, not something to commit). Open it directly
in a browser; nothing needs to be running.
"""

from __future__ import annotations

import argparse
import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# --------------------------------------------------------------------------
# Repo root discovery — mirrors sandbox/backtest/backtest/engine.py's
# find_repo_root, for consistency with the rest of the repo.
# --------------------------------------------------------------------------


def find_repo_root(start: Path) -> Path:
    for candidate in [start, *start.parents]:
        if (candidate / "contracts").is_dir() and (candidate / "CLAUDE.md").is_file():
            return candidate
    raise FileNotFoundError(f"no repo root above {start}")


# --------------------------------------------------------------------------
# Data collection
# --------------------------------------------------------------------------

LIFECYCLE_ORDER = ["research", "backtest", "paper", "live", "retired"]

STRATEGY_MANIFEST_FENCE_RE = re.compile(
    r"```strategy_manifest\s*\n(.*?)\n```", re.DOTALL
)

# YAML frontmatter block at the very top of a wiki page, e.g.:
#   ---
#   type: strategy
#   created: 2026-07-19
#   ---
# Used only as a version-ordering fallback (see _lineage_sort_key) — this is
# a narrow, single-field extraction, not a general YAML parser.
FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
CREATED_RE = re.compile(r"^created:\s*(.+)$", re.MULTILINE)

# The '## Lifecycle history' section, and the next '##'-level heading after
# it (used to find where the section ends).
LIFECYCLE_HISTORY_HEADING_RE = re.compile(
    r"^##\s+Lifecycle history\s*$", re.MULTILINE | re.IGNORECASE
)
NEXT_HEADING_RE = re.compile(r"^##\s+", re.MULTILINE)

# Trailing '-vN' version suffix on a strategy id, e.g. 'ms-shift-spy-v2' -> 2.
VERSION_SUFFIX_RE = re.compile(r"-v(\d+)$", re.IGNORECASE)


def _read_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def collect_kill_freeze(repo_root: Path) -> dict[str, bool]:
    return {
        "kill": (repo_root / "KILL").exists(),
        "frozen": (repo_root / "infra" / "paperclip" / "FROZEN").exists(),
    }


def collect_strategies(repo_root: Path) -> list[dict[str, Any]]:
    """Parse every brain/wiki/strategies/*.md page for its manifest fence.

    Each strategy page is expected to contain exactly one
    ```strategy_manifest fenced block with a JSON object matching
    contracts/strategy_manifest.schema.json. Pages that fail to parse are
    surfaced as errors rather than silently dropped, so a malformed page
    doesn't just vanish from the dashboard.
    """
    strategies_dir = repo_root / "brain" / "wiki" / "strategies"
    results: list[dict[str, Any]] = []
    if not strategies_dir.is_dir():
        return results

    for md_path in sorted(strategies_dir.glob("*.md")):
        rel_path = md_path.relative_to(repo_root).as_posix()
        try:
            text = md_path.read_text(encoding="utf-8")
        except OSError as exc:
            results.append({"error": f"{rel_path}: could not read file ({exc})", "path": rel_path})
            continue

        matches = STRATEGY_MANIFEST_FENCE_RE.findall(text)
        if len(matches) != 1:
            results.append(
                {
                    "error": f"{rel_path}: expected exactly one ```strategy_manifest block, found {len(matches)}",
                    "path": rel_path,
                }
            )
            continue

        manifest = _read_json_str(matches[0])
        if manifest is None:
            results.append({"error": f"{rel_path}: manifest block is not valid JSON", "path": rel_path})
            continue

        results.append(
            {
                "path": rel_path,
                "manifest": manifest,
                "created": _extract_frontmatter_created(text),
                "lifecycle_history": _extract_lifecycle_history(text),
            }
        )

    return results


def _read_json_str(text: str) -> Any | None:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _extract_frontmatter_created(text: str) -> str | None:
    """Pull the `created:` value out of a wiki page's YAML frontmatter.

    Only used as a fallback for lineage ordering when a strategy id has no
    detectable version suffix (see _lineage_sort_key) — deliberately not a
    real YAML parser, just enough to grab one known scalar field.
    """
    fm_match = FRONTMATTER_RE.match(text)
    if not fm_match:
        return None
    created_match = CREATED_RE.search(fm_match.group(1))
    if not created_match:
        return None
    return created_match.group(1).strip()


def _extract_lifecycle_history(text: str) -> list[str]:
    """Return each '## Lifecycle history' bullet as one flattened string,
    oldest first (document order), with the leading '- ' marker stripped.

    The section is plain markdown: nominally one bullet per line
    ('- YYYY-MM-DD — <lifecycle> — <text>'), but in practice long entries
    get hand-wrapped onto continuation lines (indented, no leading '-')
    rather than kept on one physical line. Continuation lines are folded
    back onto the bullet they belong to (joined with a space) so none of
    that text is silently dropped.
    """
    heading_match = LIFECYCLE_HISTORY_HEADING_RE.search(text)
    if not heading_match:
        return []

    rest = text[heading_match.end():]
    next_heading = NEXT_HEADING_RE.search(rest)
    section = rest[: next_heading.start()] if next_heading else rest

    bullets: list[str] = []
    current: list[str] = []
    for line in section.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            if current:
                bullets.append(" ".join(current))
            current = [stripped[2:].strip()]
        elif stripped:
            # continuation of the current bullet (or stray text before the
            # first bullet, which we just fold in rather than drop).
            current.append(stripped)
    if current:
        bullets.append(" ".join(current))
    return bullets


def collect_raw_notes(repo_root: Path) -> list[str]:
    """List every brain/raw/*.md file, repo-relative, sorted.

    Used to link strategies to research notes purely by filename
    substring match — see _linked_raw_notes.
    """
    raw_dir = repo_root / "brain" / "raw"
    if not raw_dir.is_dir():
        return []
    return sorted(p.relative_to(repo_root).as_posix() for p in raw_dir.glob("*.md"))


def _linked_raw_notes(strategy_id: str, raw_notes: list[str]) -> list[str]:
    """Raw notes whose filename contains the strategy id as a substring.

    This is a simple, naming-convention-based heuristic — there is no
    formal cross-reference field between brain/raw/ notes and strategy
    manifests in the schema, so filename substring matching is all we
    have. It can both under-match (a relevant note named without the id)
    and over-match (e.g. a hypothetical 'ms-shift-spy-v10' note's filename
    also contains 'ms-shift-spy-v1' as a substring); treat the links shown
    as a best-effort pointer, not a guaranteed/complete cross-reference.
    """
    return [note for note in raw_notes if strategy_id and strategy_id in Path(note).stem]


def _lineage_sort_key(entry: dict[str, Any]) -> tuple:
    """Order strategies within a family for the lineage view.

    Priority:
      1. A detectable trailing '-vN' version suffix on the id (e.g. 'v1'
         before 'v2') — the common case for this repo's naming, and
         unambiguous when present.
      2. The wiki page's frontmatter `created:` date, for ids with no
         version suffix — falls back to actual creation order, which is
         the next-best proxy for "lineage order" we have without a
         version marker.
      3. Plain alphabetical id, if even `created:` is missing — a strategy
         page failing to declare a page-level created date shouldn't be
         able to sort itself arbitrarily; alphabetical keeps output at
         least deterministic.
    Buckets are numbered so version-suffixed ids always sort before
    created-date-ordered ids, which sort before alphabetical-only ids;
    within a bucket the comparison is homogeneous (int, then str, then
    str), so tuple comparison never has to compare across types.
    """
    manifest = entry.get("manifest") or {}
    strategy_id = str(manifest.get("id", ""))
    created = entry.get("created")

    version_match = VERSION_SUFFIX_RE.search(strategy_id)
    if version_match:
        return (0, int(version_match.group(1)), "", strategy_id)
    if created:
        return (1, 0, str(created), strategy_id)
    return (2, 0, "", strategy_id)


def _rank_sort_key(entry: dict[str, Any]) -> tuple:
    manifest = entry.get("manifest") or {}
    scorecard = manifest.get("scorecard") or {}
    rank = scorecard.get("rank")
    # nulls last
    if rank is None:
        return (1, 0)
    return (0, rank)


def collect_promotions(repo_root: Path) -> dict[str, list[dict[str, Any]]]:
    promotions_dir = repo_root / "data" / "promotions"
    pending: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    if not promotions_dir.is_dir():
        return {"pending": pending, "rejected": rejected}

    for path in sorted(promotions_dir.glob("*.json")):
        if not path.is_file():
            continue
        rel_path = path.relative_to(repo_root).as_posix()
        data = _read_json(path)
        if data is None:
            pending.append({"error": f"{rel_path}: could not parse JSON", "path": rel_path})
            continue
        pending.append({"path": rel_path, "promotion": data})

    rejected_dir = promotions_dir / "rejected"
    if rejected_dir.is_dir():
        for path in sorted(rejected_dir.glob("*.json")):
            if not path.is_file():
                continue
            rel_path = path.relative_to(repo_root).as_posix()
            data = _read_json(path)
            if data is None:
                rejected.append({"error": f"{rel_path}: could not parse JSON", "path": rel_path})
                continue
            rejected.append({"path": rel_path, "promotion": data})

    return {"pending": pending, "rejected": rejected}


def _human_approval_complete(promotion: dict[str, Any]) -> bool:
    approval = promotion.get("human_approval") or {}
    return bool(
        approval.get("telegram_msg_id") is not None
        and approval.get("confirmation_msg_id") is not None
        and approval.get("approved_at") is not None
    )


def collect_queue(repo_root: Path) -> dict[str, Any]:
    queue_dir = repo_root / "infra" / "telegram" / "queue"
    events: list[dict[str, Any]] = []
    if not queue_dir.is_dir():
        return {"events": events, "by_severity": {}}

    for path in sorted(queue_dir.glob("*.json")):
        if not path.is_file():
            continue
        rel_path = path.relative_to(repo_root).as_posix()
        data = _read_json(path)
        if data is None:
            events.append({"path": rel_path, "severity": None, "error": True})
            continue
        events.append({"path": rel_path, "severity": data.get("severity"), "kind": data.get("kind")})

    by_severity: dict[str, int] = {}
    for evt in events:
        sev = evt.get("severity") or "unknown"
        by_severity[sev] = by_severity.get(sev, 0) + 1

    return {"events": events, "by_severity": by_severity}


def collect_postmortems(repo_root: Path) -> list[dict[str, str]]:
    postmortems_dir = repo_root / "brain" / "wiki" / "postmortems"
    results: list[dict[str, str]] = []
    if not postmortems_dir.is_dir():
        return results

    for path in sorted(postmortems_dir.glob("*.md")):
        rel_path = path.relative_to(repo_root).as_posix()
        title = path.stem
        try:
            text = path.read_text(encoding="utf-8")
            for line in text.splitlines():
                stripped = line.strip()
                if stripped.startswith("# "):
                    title = stripped[2:].strip()
                    break
        except OSError:
            pass
        results.append({"path": rel_path, "title": title})

    return results


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------

LIFECYCLE_CLASS = {
    "research": "lifecycle-research",
    "backtest": "lifecycle-backtest",
    "paper": "lifecycle-paper",
    "live": "lifecycle-live",
    "retired": "lifecycle-retired",
}

SEVERITY_CLASS = {
    "info": "sev-info",
    "warning": "sev-warning",
    "high": "sev-high",
    "critical": "sev-critical",
}


def _esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _truncate(text: str, limit: int = 200) -> str:
    """Truncate to ~limit chars on a word boundary, with a trailing ellipsis.

    Callers that need the untruncated text (e.g. for a title="" tooltip)
    should keep the original string around — this helper only returns the
    shortened display copy.
    """
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "…"


def _fmt_num(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.4f}".rstrip("0").rstrip(".") if "." in f"{value:.4f}" else f"{value:.4f}"
    return _esc(value)


def _render_kill_freeze(state: dict[str, bool]) -> str:
    if state["kill"]:
        kill_html = (
            '<div class="banner banner-kill">'
            '&#9888;&#65039; KILL SWITCH ENGAGED &mdash; repo-root <code>KILL</code> file present. '
            "All trading agents and engines must halt.</div>"
        )
    else:
        kill_html = '<div class="banner banner-clear">Kill switch: clear (no <code>KILL</code> file).</div>'

    if state["frozen"]:
        freeze_html = (
            '<div class="banner banner-frozen">'
            '&#128274; BUDGET FROZEN &mdash; <code>infra/paperclip/FROZEN</code> present. '
            "Entire loop is frozen pending human resumption.</div>"
        )
    else:
        freeze_html = '<div class="banner banner-clear">Budget freeze: clear (no <code>infra/paperclip/FROZEN</code> file).</div>'

    return kill_html + freeze_html


def _render_strategies(strategies: list[dict[str, Any]]) -> str:
    if not strategies:
        return '<p class="empty">No strategies yet &mdash; nothing in brain/wiki/strategies/.</p>'

    errors = [s for s in strategies if "error" in s]
    ok = [s for s in strategies if "manifest" in s]
    ok.sort(key=_rank_sort_key)

    rows = []
    for entry in ok:
        m = entry["manifest"]
        scorecard = m.get("scorecard") or {}
        lifecycle = m.get("lifecycle", "?")
        lifecycle_class = LIFECYCLE_CLASS.get(lifecycle, "")
        rows.append(
            "<tr>"
            f'<td><a href="../../{_esc(entry["path"])}">{_esc(m.get("id", "?"))}</a></td>'
            f'<td>{_esc(m.get("family", "?"))}</td>'
            f'<td><span class="lifecycle-badge {lifecycle_class}">{_esc(lifecycle)}</span></td>'
            f'<td>{_fmt_num(scorecard.get("sharpe_wf"))}</td>'
            f'<td>{_fmt_num(scorecard.get("sortino_wf"))}</td>'
            f'<td>{_fmt_num(scorecard.get("max_drawdown_bt"))}</td>'
            f'<td>{_fmt_num(scorecard.get("sharpe_paper"))}</td>'
            f'<td>{_fmt_num(scorecard.get("max_drawdown_paper"))}</td>'
            f'<td>{_fmt_num(scorecard.get("pnl_live"))}</td>'
            f'<td>{_fmt_num(scorecard.get("rank"))}</td>'
            "</tr>"
        )

    table = (
        '<table class="data-table">'
        "<thead><tr>"
        "<th>id</th><th>family</th><th>lifecycle</th>"
        "<th>sharpe_wf</th><th>sortino_wf</th><th>max_dd_bt</th>"
        "<th>sharpe_paper</th><th>max_dd_paper</th><th>pnl_live</th><th>rank</th>"
        "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
    )

    error_html = ""
    if errors:
        items = "".join(f"<li>{_esc(e['error'])}</li>" for e in errors)
        error_html = f'<div class="parse-errors"><strong>Parse errors:</strong><ul>{items}</ul></div>'

    return table + error_html


def _render_strategy_lineage(strategies: list[dict[str, Any]], raw_notes: list[str]) -> str:
    """Group strategies by family (lineage view), with per-strategy
    rationale and linked research notes.

    This is a second, complementary view of the same strategy data
    _render_strategies renders flat and rank-sorted above — that table is
    left untouched (it's still the right place to compare strategies
    head-to-head on the scorecard, across families); this one is about
    seeing which strategies descend from which within a family, and why
    each one is at the lifecycle stage it's at.
    """
    ok = [s for s in strategies if "manifest" in s]
    if not ok:
        return '<p class="empty">No strategies yet &mdash; nothing in brain/wiki/strategies/.</p>'

    families: dict[str, list[dict[str, Any]]] = {}
    for entry in ok:
        family = entry["manifest"].get("family") or "(no family)"
        families.setdefault(family, []).append(entry)

    blocks = []
    for family in sorted(families.keys()):
        members = sorted(families[family], key=_lineage_sort_key)

        rows = []
        for entry in members:
            m = entry["manifest"]
            strategy_id = m.get("id", "?")
            lifecycle = m.get("lifecycle", "?")
            lifecycle_class = LIFECYCLE_CLASS.get(lifecycle, "")

            history = entry.get("lifecycle_history") or []
            if history:
                latest = history[-1]
                truncated = _truncate(latest)
                if truncated != latest:
                    rationale_html = (
                        f'<span class="rationale" title="{_esc(latest)}">{_esc(truncated)}</span>'
                    )
                else:
                    rationale_html = f'<span class="rationale">{_esc(truncated)}</span>'
            else:
                rationale_html = '<span class="empty">no Lifecycle history section</span>'

            linked = _linked_raw_notes(strategy_id, raw_notes)
            if linked:
                notes_html = ", ".join(
                    f'<a href="../../{_esc(note)}">{_esc(Path(note).stem)}</a>' for note in linked
                )
            else:
                notes_html = '<span class="muted">&mdash;</span>'

            rows.append(
                "<tr>"
                f'<td><a href="../../{_esc(entry["path"])}">{_esc(strategy_id)}</a></td>'
                f'<td><span class="lifecycle-badge {lifecycle_class}">{_esc(lifecycle)}</span></td>'
                f'<td>{rationale_html}</td>'
                f'<td>{notes_html}</td>'
                "</tr>"
            )

        table = (
            '<table class="data-table lineage-table">'
            "<thead><tr><th>id</th><th>lifecycle</th>"
            "<th>latest lifecycle-history rationale</th><th>related raw notes</th>"
            "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
        )
        count_suffix = f" &mdash; {len(members)} strategies" if len(members) > 1 else ""
        blocks.append(
            f'<div class="family-block"><h3 class="family-heading">{_esc(family)}{count_suffix}</h3>'
            f"{table}</div>"
        )

    return "".join(blocks)


def _render_promotions(promotions: dict[str, list[dict[str, Any]]]) -> str:
    pending = promotions["pending"]
    rejected = promotions["rejected"]

    if not pending:
        pending_html = '<p class="empty">No pending promotions &mdash; data/promotions/ is empty or absent.</p>'
    else:
        rows = []
        for entry in pending:
            if "error" in entry:
                rows.append(
                    f'<tr class="row-error"><td colspan="5">{_esc(entry["error"])}</td></tr>'
                )
                continue
            p = entry["promotion"]
            complete = _human_approval_complete(p)
            to_stage = p.get("to_stage", "?")
            is_live_pending = to_stage == "live" and not complete
            row_class = "row-live-pending" if is_live_pending else ""
            approval_text = "approved" if complete else "AWAITING APPROVAL"
            approval_class = "approval-complete" if complete else "approval-pending"
            highlight = ' &#128680;' if is_live_pending else ""
            rows.append(
                f'<tr class="{row_class}">'
                f'<td>{_esc(p.get("strategy_id", "?"))}</td>'
                f'<td>{_esc(p.get("from_stage", "?"))} &rarr; {_esc(to_stage)}{highlight}</td>'
                f'<td><span class="{approval_class}">{approval_text}</span></td>'
                f'<td>{_esc(p.get("id", "?"))}</td>'
                f'<td>{_esc(entry["path"])}</td>'
                "</tr>"
            )
        pending_html = (
            '<table class="data-table">'
            "<thead><tr><th>strategy_id</th><th>transition</th><th>human_approval</th>"
            "<th>promotion id</th><th>file</th></tr></thead>"
            "<tbody>" + "".join(rows) + "</tbody></table>"
        )

    if not rejected:
        rejected_html = '<p class="empty muted">No rejected promotions.</p>'
    else:
        items = []
        for entry in rejected:
            if "error" in entry:
                items.append(f"<li>{_esc(entry['error'])}</li>")
                continue
            p = entry["promotion"]
            items.append(
                f'<li>{_esc(p.get("strategy_id", "?"))}: '
                f'{_esc(p.get("from_stage", "?"))} &rarr; {_esc(p.get("to_stage", "?"))} '
                f'&mdash; <code>{_esc(entry["path"])}</code></li>'
            )
        rejected_html = (
            '<details class="rejected-details"><summary>Rejected promotions '
            f"({len(rejected)})</summary><ul>" + "".join(items) + "</ul></details>"
        )

    return pending_html + rejected_html


def _render_queue(queue: dict[str, Any]) -> str:
    events = queue["events"]
    if not events:
        return '<p class="empty">Queue empty &mdash; infra/telegram/queue/ has no pending events.</p>'

    by_sev = queue["by_severity"]
    badges = []
    for sev in ["critical", "high", "warning", "info", "unknown"]:
        count = by_sev.get(sev)
        if not count:
            continue
        css = SEVERITY_CLASS.get(sev, "")
        badges.append(f'<span class="sev-badge {css}">{_esc(sev)}: {count}</span>')

    total = f'<p class="queue-total">Total pending: <strong>{len(events)}</strong></p>'
    return total + '<div class="badge-row">' + "".join(badges) + "</div>"


def _render_postmortems(postmortems: list[dict[str, str]]) -> str:
    if not postmortems:
        return '<p class="empty">No postmortems yet &mdash; nothing in brain/wiki/postmortems/.</p>'
    items = "".join(
        f'<li><a href="../../{_esc(p["path"])}">{_esc(p["title"])}</a> '
        f'<span class="muted">({_esc(p["path"])})</span></li>'
        for p in postmortems
    )
    return f"<ul class='postmortem-list'>{items}</ul>"


CSS = """
:root {
  color-scheme: light dark;
  --bg: #0b0d12;
  --panel: #151821;
  --panel-border: #262b38;
  --text: #e6e9f0;
  --muted: #8b93a7;
  --accent: #5b8cff;
  --red: #ff5c5c;
  --amber: #ffb84d;
  --green: #35c76a;
  --blue: #5b8cff;
  --gray: #8b93a7;
}
@media (prefers-color-scheme: light) {
  :root {
    --bg: #f5f6f8;
    --panel: #ffffff;
    --panel-border: #dde1e8;
    --text: #1b1f27;
    --muted: #5b6270;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.5;
}
.wrap {
  max-width: 1080px;
  margin: 0 auto;
  padding: 24px 20px 64px;
}
h1 {
  font-size: 1.5rem;
  margin-bottom: 4px;
}
.subtitle {
  color: var(--muted);
  font-size: 0.9rem;
  margin-top: 0;
  margin-bottom: 24px;
}
section {
  background: var(--panel);
  border: 1px solid var(--panel-border);
  border-radius: 10px;
  padding: 18px 20px;
  margin-bottom: 20px;
  overflow-x: auto;
}
section h2 {
  font-size: 1.05rem;
  margin-top: 0;
  margin-bottom: 12px;
}
.banner {
  padding: 12px 16px;
  border-radius: 8px;
  margin-bottom: 10px;
  font-weight: 600;
}
.banner:last-child { margin-bottom: 0; }
.banner-kill {
  background: #4a1414;
  color: #ffdada;
  border: 1px solid var(--red);
  font-size: 1.05rem;
}
.banner-frozen {
  background: #4a3414;
  color: #ffe9c2;
  border: 1px solid var(--amber);
}
.banner-clear {
  background: transparent;
  color: var(--green);
  font-weight: 500;
  border: 1px solid var(--panel-border);
}
code {
  background: rgba(128,128,128,0.15);
  padding: 1px 5px;
  border-radius: 4px;
  font-size: 0.9em;
}
table.data-table {
  border-collapse: collapse;
  width: 100%;
  font-size: 0.88rem;
}
table.data-table th, table.data-table td {
  text-align: left;
  padding: 6px 10px;
  border-bottom: 1px solid var(--panel-border);
  white-space: nowrap;
}
table.data-table th {
  color: var(--muted);
  font-weight: 600;
  text-transform: uppercase;
  font-size: 0.72rem;
  letter-spacing: 0.03em;
}
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
.lifecycle-badge {
  display: inline-block;
  padding: 2px 9px;
  border-radius: 999px;
  font-size: 0.78rem;
  font-weight: 600;
}
.lifecycle-research { background: rgba(139,147,167,0.2); color: var(--gray); }
.lifecycle-backtest { background: rgba(91,140,255,0.2); color: var(--blue); }
.lifecycle-paper { background: rgba(255,184,77,0.2); color: var(--amber); }
.lifecycle-live { background: rgba(53,199,106,0.2); color: var(--green); }
.lifecycle-retired { background: rgba(139,147,167,0.15); color: var(--muted); text-decoration: line-through; }
.empty { color: var(--muted); font-style: italic; }
.muted { color: var(--muted); }
.parse-errors { margin-top: 12px; color: var(--red); font-size: 0.85rem; }
.row-live-pending { background: rgba(255,92,92,0.12); }
.approval-complete { color: var(--green); font-weight: 600; }
.approval-pending { color: var(--red); font-weight: 700; }
.badge-row { display: flex; gap: 8px; flex-wrap: wrap; }
.sev-badge {
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 0.82rem;
  font-weight: 600;
  border: 1px solid var(--panel-border);
}
.sev-info { color: var(--gray); }
.sev-warning { color: var(--amber); }
.sev-high { color: #ff9a5c; }
.sev-critical { color: var(--red); }
.queue-total { margin-top: 0; }
.family-block { margin-bottom: 18px; }
.family-block:last-child { margin-bottom: 0; }
.family-heading {
  font-size: 0.8rem;
  margin: 0 0 8px;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  font-weight: 700;
}
.lineage-table td { white-space: normal; }
.rationale { cursor: help; }
.postmortem-list { padding-left: 20px; }
.rejected-details { margin-top: 10px; color: var(--muted); font-size: 0.85rem; }
.rejected-details summary { cursor: pointer; }
footer {
  color: var(--muted);
  font-size: 0.8rem;
  margin-top: 30px;
  border-top: 1px solid var(--panel-border);
  padding-top: 14px;
}
"""


def render(repo_root: Path) -> str:
    """Render the full status HTML for the given repo root.

    Reads current on-disk state only (strategy wiki pages, promotions,
    telegram queue, postmortems, KILL/FROZEN sentinels). Returns a
    self-contained HTML document string with inline CSS and no external
    dependencies, safe to open with no network access.
    """
    kill_freeze = collect_kill_freeze(repo_root)
    strategies = collect_strategies(repo_root)
    raw_notes = collect_raw_notes(repo_root)
    promotions = collect_promotions(repo_root)
    queue = collect_queue(repo_root)
    postmortems = collect_postmortems(repo_root)

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    body = f"""
<div class="wrap">
  <h1>Quant Platform &mdash; Local Status</h1>
  <p class="subtitle">
    Standing in for Paperclip (not installed this round &mdash; see
    infra/paperclip/README.md). Point-in-time snapshot, not live; re-run
    <code>python3 infra/dashboard/generate.py</code> to refresh.
  </p>

  <section id="kill-freeze">
    <h2>Kill / Freeze state</h2>
    {_render_kill_freeze(kill_freeze)}
  </section>

  <section id="strategies">
    <h2>Strategies &mdash; ranked by walk-forward Sharpe</h2>
    {_render_strategies(strategies)}
  </section>

  <section id="strategy-lineage">
    <h2>Strategy lineage &mdash; by family</h2>
    {_render_strategy_lineage(strategies, raw_notes)}
  </section>

  <section id="promotions">
    <h2>Pending promotions</h2>
    {_render_promotions(promotions)}
  </section>

  <section id="queue">
    <h2>Telegram event queue</h2>
    {_render_queue(queue)}
  </section>

  <section id="postmortems">
    <h2>Recent postmortems</h2>
    {_render_postmortems(postmortems)}
  </section>

  <footer>
    Generated at {_esc(generated_at)} from {_esc(str(repo_root))}. This is a
    point-in-time snapshot produced by a static scan of the repo &mdash;
    it does not poll, run, or watch anything.
  </footer>
</div>
"""

    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "<title>Quant Platform &mdash; Local Status</title>\n"
        f"<style>{CSS}</style>\n"
        "</head>\n"
        f"<body>{body}</body>\n"
        "</html>\n"
    )


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the local quant-platform status dashboard.")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output path for the rendered HTML (default: infra/dashboard/status.html)",
    )
    args = parser.parse_args()

    repo_root = find_repo_root(Path(__file__).resolve().parent)
    out_path = args.out if args.out is not None else repo_root / "infra" / "dashboard" / "status.html"

    html_str = render(repo_root)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html_str, encoding="utf-8")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
