# P11 — Integration loop: seams and what leaked

`run_loop.sh` drives one full loop on the `sma-cross-demo` toy strategy and
marks any broken seam with `>>> LEAK`. It runs unattended except that the
Telegram approval is injected exactly as the bridge's two-step flow would
write it (so CI can run it without a human tap).

## The loop

```
research ─(ranker, auto)→ backtest ─(harness)→ backtest_result.json + ruleset.json
   → ranker(threshold) → paper ─(paper-engine, sim feed)→ paper_result.json
   → ranker → live REQUEST (blocks) → Telegram /approve + CONFIRM
   → live dry-run (sim broker) → live_journal.jsonl → postmortem in vault
```

## Seams exercised (each an independent failure point)

| # | Seam | What proves it |
|---|------|----------------|
| 1 | brain → ranker | ranker reads the wiki manifest block, auto-promotes research→backtest once the signal file exists |
| 2 | harness → contract | backtest emits a schema-valid `backtest_result.json` **and** the ADR-0002 `ruleset.json` handoff |
| 3 | ranker thresholds | promote-or-retire decision against `promotion_thresholds.toml` |
| 4 | Python fit → Rust engine | paper-engine consumes `ruleset.json`, runs the sim feed, emits `paper_result.json` |
| 5 | **safety gate** | live engine **refuses to start** while `human_approval` is incomplete |
| 6 | Telegram two-step | `/approve` → `CONFIRM <id>` writes both message ids into the promotion record |
| 7 | live dry-run | live engine starts only after approval, journals state (crash-recoverable) |
| 8 | value backprop | postmortem generated from real result files, linked into the vault |

## Known, intentional behaviours (not leaks)

- **The toy strategy retires at the thresholds.** A 20/50 SMA cross on a
  random-walk snapshot has no real edge, so the ranker correctly retires it
  at both the backtest and paper gates. That *is* the pipeline working. To
  still exercise seams 5–8, the script forces the lifecycle forward and
  seeds a live promotion request — clearly logged as a `note:`.
- **The approval is simulated.** Seam 6 calls the bridge's own
  `start_approval`/`confirm_approval` with the exact `CONFIRM <id>` reply,
  i.e. the code path a real tap triggers. On the WSL host with a real bot,
  the human taps instead; nothing else changes.
- **Feeds are the sim feed / sim broker.** No network. The Alpaca paper
  endpoint is the same code path behind `--mode dry-run` (seam 7 uses
  `--mode sim` so CI stays offline); switching to `dry-run` on the host
  exercises real Alpaca auth with zero dollars.

## Residual seams to watch on the real host (can't be tested offline)

1. Alpaca paper-endpoint auth + order acknowledgement latency (dry-run).
2. Real Telegram delivery + the owner-id allowlist against a live bot.
3. Obsidian graph actually rendering the new postmortem links (cosmetic).
4. Paperclip firing the heartbeats that this script runs by hand.

## Run it

```sh
bash tests/integration/run_loop.sh    # exits non-zero if any seam leaks
```
