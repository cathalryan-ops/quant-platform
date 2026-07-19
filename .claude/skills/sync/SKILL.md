---
name: sync
description: Batch-process every unprocessed source in brain/raw/ into the wiki (runs /capture over the inbox), then reconcile index.md. Use on a schedule or when the inbox has accumulated.
---

# /sync

1. List `brain/raw/`; skip files whose first line is an
   `<!-- processed: ... -->` stamp.
2. Run the /capture procedure for each remaining file, oldest first.
3. After the batch: verify every `wiki/` page appears in `index.md` exactly
   once and every index entry points at a real file; fix drift.
4. Append a closing `log.md` line: `- YYYY-MM-DD — sync — N sources
   processed, M pages touched`.
5. If the inbox was empty, do nothing and say so — never invent work.
