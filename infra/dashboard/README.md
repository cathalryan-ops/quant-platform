# infra/dashboard

Paperclip is the platform's intended dashboard, but it is **not installed**
this round (only its config was hardened under `infra/paperclip/`). That
leaves no way to see the loop's state at a glance, so this is a lightweight
stand-in: a stdlib-only Python script that scans the repo's current on-disk
state (kill/freeze sentinels, strategy manifests, pending promotions,
Telegram queue depth, postmortems) and renders it as one static HTML file.

No server, no build step, no external dependencies, no network access
required.

## Regenerate

```
python3 infra/dashboard/generate.py
```

This writes `infra/dashboard/status.html` (gitignored — it's a generated
snapshot of live, frequently-changing state, not source). Pass `--out PATH`
to write somewhere else.

## View

Just open `infra/dashboard/status.html` directly in a browser. There is
nothing to run and nothing to connect to — it's a static file.

## What it shows

- Kill switch (`<repo_root>/KILL`) and budget freeze
  (`infra/paperclip/FROZEN`) state.
- Every strategy in `brain/wiki/strategies/*.md`, parsed from its
  ` ```strategy_manifest ` fenced block, with lifecycle and scorecard.
- Pending promotions from `data/promotions/*.json`, with rejected ones
  (`data/promotions/rejected/`) listed separately/collapsed. Promotions to
  `live` still awaiting human approval are highlighted.
- Telegram queue depth from `infra/telegram/queue/*.json` (excluding
  `sent/`), broken down by severity.
- Recent postmortems from `brain/wiki/postmortems/*.md`.

It is a point-in-time snapshot, not a live view — re-run the script to
refresh.

## Tests

```
python3 -m unittest infra/dashboard/test_generate.py -v
```

Stdlib `unittest` only, no pytest.
