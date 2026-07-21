# Pinned data snapshots

Every backtest runs from a content-hashed parquet under
`data/us_equities/daily/` (gitignored — reproducible via the fetch +
content-hash pin below, not via committing the file itself). A strategy's
runner script pins the exact hash it expects; a run whose file no longer
matches that hash aborts rather than silently running on different data.
See `backtest/data.py`.

## `QQQ_SPY_2016-01-01_2024-12-31.parquet`

- **Universe (2):** SPY, QQQ
- **Period:** 2016-01-01 to 2024-12-31
- **Content hash:** `sha256:abffe4a6eae63b29c4edd312615b1b8a234d39a1ad662d3c377cd511ad687c75`
- **Used by:** every strategy proposed before 2026-07-21 (ms-shift-spy,
  ms-shift-spy-high-displacement, mean-reversion-spy-qqq,
  ms-shift-spy-vol-regime, tsmom-spy-qqq and its vol-overlay follow-ups,
  turn-of-month-spy-qqq, 52wk-high-spy-qqq).
- Two highly correlated large-cap US equity index ETFs — sufficient for
  every single-asset (absolute momentum, mean-reversion, structure-break,
  calendar) hypothesis tested so far, but has no basket to rank or
  diversify across.

## `DIA_GLD_IWM_QQQ_SPY_TLT_XLB_XLE_XLF_XLI_XLK_XLP_XLRE_XLU_XLV_XLY_2016-01-01_2024-12-31.parquet`

- **Universe (16):** SPY, QQQ, IWM, DIA (broad index breadth across
  market-cap tiers); XLK, XLF, XLE, XLV, XLI, XLY, XLP, XLU, XLB, XLRE
  (10 of the 11 SPDR Select Sector ETFs); TLT, GLD (non-equity
  diversifiers)
- **Period:** 2016-01-01 to 2024-12-31 (all 16 symbols align cleanly,
  2263 sessions, 2016-01-04 to 2024-12-30 — no truncation)
- **Content hash:** `sha256:499059d460fe88bdf438ba4746151a42ba57c96fbf068ca24190174a41419bb6`
- **Fetched by:** `scripts/fetch_wider_universe.py` (re-run to refresh;
  it no-ops if the file already exists)
- **Why this basket:** every prior strategy in this vault is single-asset
  (absolute time-series signals scored independently per symbol) because
  SPY+QQQ don't support anything else. This unlocks cross-sectional
  strategies that need to rank or compare assets against each other —
  sector rotation (10 sectors), multi-asset trend/dual-momentum (equities
  vs. bonds vs. gold), or relative strength across market-cap tiers.
- **XLC (Communication Services) deliberately excluded:** it didn't
  launch until 2018-06-19. `close_matrix`/`bar_frame` inner-join on dates
  where every symbol in the universe has a bar, so including a symbol
  with a shorter history silently truncates every OTHER symbol's usable
  range too — including it would have cut 2016-2018 off the whole
  snapshot, not just off XLC.
