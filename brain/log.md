# Brain Log

Chronology of every ingestion and vault operation. Append-only.

- 2026-07-19 — vault skeleton created (P0 scaffold).
- 2026-07-19 — capture — raw/sample-market-structure-primer.md -> concepts/market-structure-shift.md (new)
- 2026-07-19 — capture — raw/sample-market-structure-primer.md -> concepts/displacement.md (new)
- 2026-07-19 — sync — 1 source processed, 2 pages touched
- 2026-07-19 — proposal — research orchestrator accepted strategies/ms-shift-spy.md (ms-shift-spy-v1, lifecycle research)
- 2026-07-19 — digest — 1 proposal, 2 concept pages summarised to Telegram queue
- 2026-07-19 — postmortem — worked example postmortems/ms-shift-spy-example.md linked to strategies/ms-shift-spy.md (P9 demo)
- 2026-07-20 — retired — real walk-forward backtest of ms-shift-spy-v1 failed backtest->paper gate (Sharpe 0.674 vs min 1.0); manually recorded (data/ gitignored, not reproducible from this repo)
- 2026-07-20 — research — filed and resolved fold-regime hypothesis for ms-shift-spy-v1: 12-fold re-run falsifies the "2022 whipsaw" theory; edge looks concentrated in a few post-shock continuation windows rather than regime-conditional (brain/raw/ms-shift-spy-v1-fold-regime-hypothesis.md)
- 2026-07-20 — proposal — filed strategies/ms-shift-spy-high-displacement.md (ms-shift-spy-v2, lifecycle research), a single-variable follow-up to ms-shift-spy-v1's retirement; displacement_mult 1.5->2.0, value chosen via synthetic firing-frequency calibration (3.0 fired zero times, 2.0 chosen as a meaningful-but-not-reckless step); index.md corrected to show ms-shift-spy as retired (was stale at research)
- 2026-07-20 — retired — ms-shift-spy-v2 real backtest: Sharpe 0.813341 (vs min 1.0), Sortino 1.199802 (vs min 1.2, missed by 0.0002), max drawdown 1.18%. Directionally confirms the displacement-filter hypothesis (turnover halved, Sharpe up ~24% vs v1) but still fails the gate. Flagged: no further displacement_mult tuning on this same 2016-2024 sample (overfitting risk); identified risk.stop_loss_pct is declared in the manifest but never enforced in the backtest engine (vbt.Portfolio.from_orders has no sl_stop) as the more promising structurally-different next lever.
- 2026-07-20 — capture — created concepts/stop-loss-rearm-coupling.md: root-causes why enforcing risk.stop_loss_pct made ms-shift-spy-v1/v2 worse (a re-arm rule coupled to the same rare reversal event the signal itself uses), documents the "Option C" combined re-arm fix and its out-of-sample validation (oos.py, trailing 25% holdout over the 2022-10-2023-07 QQQ lockout fold): true original design OOS-rejected on both strategies, Option C passes cleanly on both.
- 2026-07-20 — research — strategies/ms-shift-spy.md Lifecycle history: appended stop-loss-enforcement + Option C OOS-validation finding, linked to the new concept page; lifecycle stays retired (passed_thresholds still false with Option C, Sharpe ~0.63 < 1.0 minimum).
- 2026-07-20 — research — strategies/ms-shift-spy-high-displacement.md Lifecycle history: same update as v1, linked to the new concept page; lifecycle stays retired (passed_thresholds still false with Option C, Sharpe ~0.76 < 1.0 minimum).
