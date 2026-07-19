---
name: lint
description: Repair vault integrity — orphan pages, broken wikilinks, index.md drift, invalid strategy_manifest blocks, unsourced claims. Run nightly or after manual vault edits.
---

# /lint

Check and repair, reporting every fix:

1. **Index drift** — every `wiki/**/*.md` page (except `_templates/`) has
   exactly one `index.md` line in the right section; every index entry
   resolves to a real file. Fix both directions.
2. **Broken links** — every `[[wikilink]]` resolves to a page. Fix the
   spelling if the target is obvious; otherwise flag it in the report.
3. **Orphans** — pages with no inbound AND no outbound wikilinks. Add the
   natural links if they exist; otherwise flag.
4. **Manifest validity** — every `strategies/` page has exactly one fenced
   `strategy_manifest` block that parses and validates against
   `contracts/strategy_manifest.schema.json` (check with:
   `cd sandbox/backtest && uv run python -c "import json,sys,contracts;
   contracts.StrategyManifest.model_validate(json.loads(sys.stdin.read()))"`).
   Invalid blocks are flagged, never auto-edited — lifecycle/scorecard
   fields belong to the ranker.
5. **Deletions** — `git diff` the vault; if wiki content was deleted rather
   than superseded, restore it and flag.
6. Append one `log.md` line summarising: `- YYYY-MM-DD — lint — X fixed,
   Y flagged`.

Never "fix" by deleting knowledge. When in doubt, flag.
