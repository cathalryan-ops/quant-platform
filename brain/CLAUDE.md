# Brain — Vault Schema (Karpathy LLM Wiki)

This directory is an Obsidian vault and the platform's long-term memory.
The root constitution applies; these rules govern the vault itself. The four
vault operations are Claude Code skills: `/capture`, `/sync`, `/lint`,
`/digest` (defined in `.claude/skills/`).

## Layout & flow

- `raw/` — inbox. Sources land here untouched (articles, paper notes, chat
  extracts). Nothing in `raw/` is trusted knowledge until processed.
- `wiki/` — atomic notes, one topic per page, densely `[[wikilinked]]`.
  - `strategies/` — one page per strategy; **single source of truth** for
    its lifecycle and scorecard.
  - `concepts/` — indicators, market structure, mechanisms, paper findings.
  - `postmortems/` — one page per reviewed paper/live session.
  - `_templates/` — canonical page skeletons. Always start from these.
- `index.md` — catalog of every wiki page, one line each. No orphans.
- `log.md` — append-only chronology of every vault operation.

## Page rules

1. Filenames are kebab-case; one `# H1` per page matching the filename's
   meaning. YAML frontmatter with `type` (strategy|concept|postmortem) and
   `created` (YYYY-MM-DD).
2. **Strategy pages embed a fenced `strategy_manifest` code block** whose
   JSON validates against `contracts/strategy_manifest.schema.json`. This
   block is how the sandbox discovers candidates; edit lifecycle/scorecard
   ONLY here. Fence tag: ` ```strategy_manifest `.
3. Every factual claim links its source: a `raw/` file or a result file
   path. Unsourced claims are `/lint` findings.
4. Cross-reference generously with `[[wikilinks]]`; a page with no inbound
   or outbound links is an orphan (a `/lint` finding).
5. Never delete content. Supersede: strike the old text or move it to a
   "Superseded" section with a dated note saying why.

## Processing rules (used by /capture and /sync)

- Processing a raw file = extract atomic notes into `wiki/` (create or
  extend pages), add `[[wikilinks]]` both ways where topics touch, update
  `index.md`, append one `log.md` line per page touched.
- **Idempotence:** after processing, stamp the raw file's first line with
  `<!-- processed: YYYY-MM-DD -->`. Stamped files are skipped; re-running
  /sync is always safe.
- A raw source proposing a tradeable edge does NOT create a strategy page
  directly — it creates/extends concept pages. Strategy pages are created
  by the research orchestrator (P3) with a falsifiable hypothesis and a
  draft manifest at `lifecycle: research`.

## log.md format

`- YYYY-MM-DD — <operation> — <detail>` (one line per action, append-only).
