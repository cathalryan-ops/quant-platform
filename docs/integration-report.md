# P11 — Integration loop report (2026-07-19)

`scripts/integration_loop.py` runs the full compounding loop on a toy
strategy (`sma-cross-loop-v1`) in a scratch copy of the repo layout:
seed → research page → ranker (research→backtest) → walk-forward backtest
against a pinned trending snapshot passing the REAL thresholds (Sharpe 4.6)
→ ruleset export → ranker (backtest→paper) → Rust paper engine, 120 sim
sessions, 102 trades → ranker issues a live promotion request and BLOCKS →
two-step Telegram approval (the only manual tap; exercised via the bridge's
own core functions) → ranker (paper→live) → Rust live engine dry loop with
sim broker, including a restart proving order-id idempotency → postmortem
page + follow-up research task (P9's value backprop).

**Result: 14/14 seams OK, unattended except the approval tap.**

## Seams that leaked during construction (fixed)

1. **Rust binaries assumed they run inside the repo** — `cargo run` from
   the scratch root couldn't find the workspace. Fixed by invoking with
   `--manifest-path` while keeping cwd in the scratch root (which is what
   `find_repo_root` keys off). Deployment lesson: systemd units must set
   `WorkingDirectory` to the repo root.
2. **Session count vs. signal lookback** — a 15-session paper run produced
   zero trades because SMA(20/50) needs 50 bars of history before its
   first signal. The result was "valid" but vacuous. The loop now runs 120
   sessions and asserts `num_trades > 0`; the ranker-facing lesson is that
   `min_paper_days` must exceed the strategy's lookback to be meaningful.

## Honesty note

The scratch copy relaxes only `[paper_to_live]` thresholds (a short
synthetic paper session cannot establish a Sharpe); the backtest gate runs
against the ratified thresholds unchanged, and no repo config is touched.
