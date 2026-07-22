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

## `BTCUSD_ETHUSD_2021-01-01_2024-12-31.parquet` (`data/crypto/daily/`)

- **Market:** `crypto` (the first non-`us_equities` pinned data in this
  vault; see `contracts/strategy_manifest.schema.json`'s `market` enum).
  Symbols are stored in Alpaca's pair format with the `/` intact (`BTC/USD`,
  `ETH/USD`) — only the filename strips it (`BTCUSD`), since `/` is a path
  separator. `backtest/engine.py` annualizes crypto Sharpe/Sortino with
  365 sessions/year (`SESSIONS_PER_YEAR["crypto"]`), not equities' 252 —
  every calendar day has a bar here (24/7 spot trading, confirmed no
  weekend/holiday gaps: exactly 1461 bars/symbol for a 4-year span).
- **Universe (2):** BTC/USD, ETH/USD — the two most liquid USD crypto spot
  pairs Alpaca offers, deliberately small and liquid rather than broad.
- **Period:** 2021-01-01 to 2024-12-31 (both symbols align cleanly, 1461
  sessions, no truncation). **Shorter than the equity snapshots' 2016-2024
  window** — Alpaca's crypto bar history starts 2021-01-01; requesting
  from 2016-01-01 empirically returns data only from 2021-01-01 on.
- **Content hash:** `sha256:096c4fe845e542a6756a35c18c25903f06aadc6068464e0a68ad82a63301f355`
- **Fetched by:** `scripts/fetch_crypto_universe.py` (re-run to refresh;
  it no-ops if the file already exists). Same `ALPACA_API_KEY`/
  `ALPACA_SECRET_KEY` as the equity fetch — no new credentials.
- **Why:** 13 real walk-forward backtests across structurally distinct
  mechanisms have converged on a Sharpe ~0.6-0.9 ceiling on the same
  US-equity/sector daily universe (see
  `brain/wiki/postmortems/research-campaign-2026-07-21.md` and
  `brain/wiki/postmortems/pinned-universe-diversity-2026-07-22.md`) — a
  pattern across unrelated mechanisms that looks like a property of the
  data/universe, not of signal design. This pins a genuinely different
  asset class (24/7, different vol/liquidity regime, no overnight-gap
  structure) to test that directly, reusing already-proven mechanisms
  (tsmom, ms-shift) rather than inventing a new one.
