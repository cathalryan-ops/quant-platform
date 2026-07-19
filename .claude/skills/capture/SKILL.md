---
name: capture
description: Ingest ONE source from brain/raw/ into the wiki — extract atomic notes, add wikilinks, update index.md, append to log.md. Use when the user points at a specific raw file; use /sync to batch-process the whole inbox.
---

# /capture <raw-file>

Process a single `brain/raw/` file into the vault, per `brain/CLAUDE.md`.

1. If the file's first line is an `<!-- processed: ... -->` stamp, stop and
   say so (idempotence).
2. Read the source fully. Identify the atomic topics it actually supports —
   concepts, mechanisms, evidence. Quality over coverage.
3. For each topic: create a page from `brain/wiki/_templates/concept.md`
   (or extend the existing page — check `index.md` first). Every claim
   cites the raw file with a markdown link. Add `[[wikilinks]]` in both
   directions to touching pages.
4. Update `brain/index.md` (one line per new page, correct section).
5. Append one `brain/log.md` line per page created/extended.
6. Stamp the raw file's first line: `<!-- processed: YYYY-MM-DD -->`.
7. Never create strategy pages here — that is the research orchestrator's
   job (see brain/CLAUDE.md processing rules).
