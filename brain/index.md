# Brain Index

Catalog of every wiki page. Maintained by the vault operations (`/capture`,
`/sync`, `/lint`) — see `brain/CLAUDE.md`.

## Strategies

- [[ms-shift-spy]] — ms_shift on SPY/QQQ; displacement-filtered
  structure breaks; `retired` (failed backtest→paper gate, real 2016-2024
  data; see Lifecycle history for the fold-regime follow-up).
- [[ms-shift-spy-high-displacement]] — v2, single-variable follow-up
  raising the displacement threshold 1.5x→2.0x ATR; `retired` (Sharpe
  0.813, close on Sortino but still failed the gate — see Lifecycle
  history for the stop-loss-gap finding it points to next).
- [[mean-reversion-spy-qqq]] — structurally distinct from `ms_shift`: buys
  an outsized single-day drop, holds a fixed 5-session horizon; `retired`
  (Sharpe 0.023 — no gate near-miss, and the mechanism-level test found no
  real reversion effect at all).
- [[ms-shift-spy-vol-regime]] — v1's unchanged signal gated to a trailing
  volatility band [12%, 35%] instead of v2's displacement-magnitude axis;
  `retired` (Sharpe 0.120, worse than v1's ungated baseline — the gate
  preserved the strong folds but turned previously-positive folds
  negative).
- [[tsmom-spy-qqq]] — structurally orthogonal to the whole `ms_shift`/
  mean-reversion line: 12-1 time-series momentum, no day-scale event, held
  for as long as the trailing 12-month trend stays positive; `retired`
  (Sharpe 0.813 misses the gate by the same margin as v2, but Sortino
  clears 1.2 and OOS improves on in-sample with zero fit parameters — a
  clean near-miss, not a fitted one — though the pre-registered
  falsification test also triggers: fully invested through the 2020
  COVID crash).
- [[tsmom-vol-accel]] — single-variable follow-up to tsmom-spy-qqq: gates
  the unchanged signal off when 5-day realized vol expands past 1.75x its
  63-day baseline, aimed at tsmom's COVID-crash blind spot; `retired`
  (Sharpe 0.534, worse than the ungated baseline — the gate genuinely
  raised COVID-window flat time from 0% to ~47% as designed, but more
  than doubled turnover, and the added whipsaw cost outweighs the
  crash-window benefit).
- [[tsmom-vol-accel-hysteresis]] — single-variable follow-up to
  tsmom-vol-accel: adds a lower re-entry threshold (1.25 vs the unchanged
  1.75 exit) to cut gate chatter; `retired` (Sharpe 0.608 — every
  prediction came true in direction, turnover down 13.4%, COVID
  protection preserved and improved, but the magnitude wasn't enough to
  close the gap to the ungated baseline; axis closed, flagged next step
  is continuous vol-targeting sizing instead of a binary gate).
- [[tsmom-vol-target]] — structurally different follow-up to the whole
  vol-gate line: replaces the binary gate with continuous vol-targeted
  sizing (`min(1.0, 0.15/realized_vol)`); `retired` (Sharpe 0.742 —
  turnover problem fully solved (0.496, essentially the ungated
  baseline's 0.465) and COVID exposure genuinely scaled down (~39% avg
  weight), but still short of the ungated baseline because raw vol level
  scales down good high-vol folds along with bad ones; closes the
  vol-overlay branch of the momentum line with a clean, complete finding).
- [[turn-of-month-spy-qqq]] — first calendar-only hypothesis, no price
  data at all: long the last trading day of the month through the first
  three of the next; `retired` (Sharpe 0.022, a clean null — the
  falsification test failed outright, in-window returns mildly *lower*
  than out-of-window on both symbols, no trace of the effect in this
  sample).
- [[52wk-high-spy-qqq]] — structurally different construction from
  tsmom: price-to-rolling-max ratio (anchoring-bias mechanism, George &
  Hwang 2004) rather than a trailing return; `retired` (Sharpe 0.625,
  meaningfully below tsmom-spy-qqq's 0.813 — ~80% raw-signal agreement
  with tsmom means this is a related but not fully independent bet, and
  it nets out worse with more than double the turnover, suggesting the
  max-ratio construction chatters near its threshold more).
- [[sector-rotation]] — first cross-sectional strategy in this vault:
  ranks the 10 SPDR sector ETFs against each other monthly, holds the
  top 3; `retired` (Sharpe 0.255, a clear miss, highest drawdown and
  second-highest turnover recorded here — genuinely rotates (32 distinct
  3-sector combinations) but XLK dominates 69.1% of selections, so this
  mostly found tech's 2016-2024 dominance rather than validating
  cross-sectional momentum broadly).
- [[cross-sectional-momentum-stocks50]] — same mechanism as
  sector-rotation, run on a newly pinned 50-single-name-stock universe
  (~4-5 per GICS sector) instead of 10 sector ETFs, to test whether real
  idiosyncratic dispersion changes the result; `retired` (Sharpe 0.280,
  same order of magnitude as sector-rotation's 0.255 — falsification
  test passed far more cleanly (93 distinct 15-stock combos, all 50
  names used, no XLK-style dominance) but turnover is ~5x worse and OOS
  Sharpe degrades -44.2% instead of improving, the first strategy here
  to break that pattern; see [[universe-scale-2026-07-22]]).
- [[dual-momentum-equity-bond-gold]] — second cross-sectional strategy,
  first spanning multiple asset classes: ranks SPY/TLT/GLD monthly,
  holds the leader only if its own momentum is positive, else cash;
  `retired` (Sharpe 0.101, worse than both concepts it composes —
  drawdown genuinely improved (1.401%, among the lowest recorded) and
  the cash floor genuinely binds (21.3% of rebalances) — mechanism
  verified real, just not profitable on this three-asset basket).
- [[tsmom-breadth-gate]] — third follow-up gate on tsmom-spy-qqq, first
  cross-sectional (not self-referential) gate: closes when <50% of the
  10 sectors are themselves trending up; `retired` (Sharpe 0.559 vs.
  the 0.813 ungated baseline — gate genuinely binds (78/125 sessions
  beyond the base signal's own flat days) but turnover +61% swamps a
  ~0.7% drawdown improvement, the same shape as the earlier vol-gate
  line — now three structurally different gate types have all made this
  signal worse, closing the gating axis for now).
- [[tsmom-ms-shift-blend]] — equal-weight blend of tsmom-spy-qqq and
  ms-shift-spy-high-displacement, first strategy to combine two edges
  instead of gating one; `retired`, the **best result in this vault**:
  Sharpe 0.884 and Sortino 1.297 (clears the 1.2 gate outright), beating
  both legs on every metric, driven by a confirmed moderate (0.5522)
  correlation between the two legs — still short of the 1.0 Sharpe gate.
  **2026-07-22:** the human reviewed and declined to loosen the gate to
  rescue this result (it's written into this strategy's own kill
  criterion); stays `retired`, no paper promotion. `contracts/
  promotion_thresholds.toml` unchanged.
- [[tsmom-btc-eth]] — first strategy in this vault on a market other
  than `us_equities`: [[time-series-momentum]] reused unmodified
  (calendar-day-adjusted lookback=365/skip=30) on BTC/USD, ETH/USD,
  testing whether the equity-universe's Sharpe ~0.6–0.9 ceiling (13
  strategies, see research-campaign-2026-07-21) is a data/universe
  property rather than a mechanism-design one. `retired`: Sharpe 0.219,
  a clear miss — the mechanism's asymmetric shock-protection pattern
  replicated faithfully (correctly flat through the Nov-2022 FTX
  collapse, unlike tsmom-spy-qqq's COVID result), but aggregate Sharpe
  is well below both the gate and the equity baseline, driven by 3
  flat folds of 8 and 65% higher turnover. Evidence against the simple
  "different asset class unlocks a better result" hypothesis. Required
  a small contracts/engine patch to enable `market: "crypto"` (schema +
  per-market 365-day annualization in engine.py/oos.py).

- [[tsmom-ms-shift-dualmom-blend]] — 3-way equal-weight (1/3 each) blend
  extending [[tsmom-ms-shift-blend]] with a third leg,
  [[dual-momentum-equity-bond-gold]]; `retired` (Sharpe 0.863027, below
  the 2-leg blend's 0.884266 — misses its own pre-registered kill
  criterion. Sortino/drawdown/turnover all improve slightly, but the
  third leg's correlation to tsmom-spy-qqq (0.5852) turned out higher
  than tsmom and ms-shift's correlation to each other (0.5522), driven by
  shared SPY-momentum logic — less independent a leg than screening
  hoped).
- [[tsmom-tlt-gld]] — [[time-series-momentum]] unmodified, applied
  independently to TLT and GLD (zero symbol overlap with the existing
  blend legs); `retired` on the standalone gate (Sharpe 0.173042, a
  clear miss) but the correlation finding is the real result: 0.0051 vs
  tsmom-spy-qqq and 0.0689 vs ms-shift-spy-high-displacement — near-zero,
  unlike dual-momentum-equity-bond-gold's 0.5852. Weak-but-real edge
  (not a mechanism-level null), immediately tested as a blend leg — see
  [[tsmom-ms-shift-tltgld-blend]].
- [[tsmom-ms-shift-tltgld-blend]] — 3-way equal-weight blend extending
  [[tsmom-ms-shift-blend]] with [[tsmom-tlt-gld]] as the third leg
  (chosen over dual-momentum for its near-zero correlation to both
  existing legs); `retired`, the **new best result in this vault**:
  Sharpe 0.989632, Sortino 1.506836, missing the 1.0 Sharpe gate by only
  0.010368 (1.0%) — the closest any strategy here has ever come. Beats
  the 2-leg blend by +0.105, in direct contrast to the dual-momentum
  3rd-leg attempt's -0.021 regression, confirming correlation regime
  (near-zero: 0.0051/0.0689) rather than standalone Sharpe strength
  determines whether a third leg helps.
- [[ms-shift-btc-eth]] — [[market-structure-shift]]/[[displacement]]
  unmodified, applied to BTC/USD, ETH/USD; `retired` (Sharpe 0.559667,
  a clear miss but the strongest single-leg crypto result so far — 44%
  short of the gate vs. tsmom-btc-eth's 78% short. Moderate correlation
  to tsmom-btc-eth, 0.4319, and near-coin-flip raw signal agreement,
  45.9-50.4%).
- [[ms-shift-tsmom-blend-btc-eth]] — crypto-native analog of
  [[tsmom-ms-shift-blend]]: blends [[ms-shift-btc-eth]] and
  [[tsmom-btc-eth]] 50/50; `retired` (Sharpe 0.406965, *below*
  ms-shift-btc-eth alone — the opposite outcome from the equity blend
  despite comparable leg correlation. Root cause: the two crypto legs
  are 2.55x apart in individual strength, and equal-weighting between
  unequal-strength legs dilutes more than moderate correlation
  compensates for. Refines the correlation-over-strength finding from
  [[blend-leg-search-2026-07-22]]: correlation is necessary but not
  sufficient — comparable leg strength matters too).
- [[low-vol-anomaly-stocks50]] — first strategy in this vault on a
  mechanism outside momentum/structure-break/mean-reversion/calendar:
  ranks the 50-stock universe by trailing realized volatility, holds the
  15 least volatile; `retired` (Sharpe 0.518773 — best cross-sectional
  result here so far, but the falsification check found the anomaly
  inverted on this sample: the low-vol basket's raw Sharpe, 0.5386, is
  below an equal-weight buy-and-hold benchmark's, 0.6608; see
  [[low-vol-anomaly-2026-07-22]]).
- [[pairs-trading-stocks50]] — first long-short, market-neutral strategy
  in this vault: three same-sector pairs (JNJ/ABT, CVX/COP, DUK/SO)
  pre-screened via Engle-Granger cointegration (p<0.05 full-sample),
  trading a 60-day rolling-hedge-ratio spread; `retired`, this vault's
  first *negative* walk-forward Sharpe (-0.539613) — the cointegration
  screen turned out to be spurious (none of the three pairs hold up when
  the test is re-run on each half of the sample separately, p=0.25-0.33);
  see [[pairs-trading-stocks50-2026-07-22]].
- [[sma-cross-demo]] — trivial 20/50-day SMA crossover on SPY, the P11
  integration-test scaffold that drives the full loop end-to-end; not a
  real edge and excluded from cross-strategy synthesis. `research`
  (harness demo only — never intended to be retired/promoted).

## Concepts

- [[market-structure-shift]] — decisive break of the prevailing swing
  sequence; core setup of the `ms_shift` family.
- [[displacement]] — wide-range confirmation of a break; the quality filter
  for structure shifts.
- [[stop-loss-rearm-coupling]] — why gating a stop's re-arm on the same
  rare event a trend-persistent signal uses to reverse can lock a position
  out of the exact recovery that would have vindicated it; the "Option C"
  fix and its OOS validation on ms-shift-spy-v1/v2.
- [[time-series-momentum]] — an asset's own trailing return predicts its
  near-term drift; absolute (not cross-sectional), month-scale, and blind
  to shocks inside its own lookback window.
- [[volatility-acceleration]] — short-window realized vol vs. its own
  longer-window baseline; a fast, relative, self-referential regime-change
  detector, distinct from a static absolute vol band.
- [[volatility-targeting]] — continuous, threshold-free position scaling
  inversely with realized vol; no gate to chatter across, but doesn't
  distinguish "good" (rally) vol from "bad" (crash) vol.
- [[turn-of-month-effect]] — returns cluster around month boundaries
  (institutional-flow-driven, not information-driven); the first
  calendar-only, price-independent mechanism tested in this vault.
- [[fifty-two-week-high-effect]] — price proximity to its own trailing
  52-week high predicts continuation via anchoring bias, a different
  causal claim (and different arithmetic — ratio to a rolling max, not a
  trailing return) than [[time-series-momentum]].
- [[cross-sectional-momentum]] — rank a basket against EACH OTHER's
  trailing return and rotate into the relative leaders, as opposed to
  time-series-momentum's absolute (judge-against-own-history)
  construction; the first mechanism in this vault needing a basket, not
  a single asset.
- [[dual-momentum]] — composes time-series-momentum's absolute floor
  with cross-sectional-momentum's relative rank: hold the basket's
  leader only if it also clears its own trend test, else cash; the
  mechanism that lets a basket-relative signal go flat instead of always
  owning whichever candidate is least bad.
- [[market-breadth]] — fraction of a basket independently confirming a
  trend, used to gate a decision on a DIFFERENT asset rather than to
  pick which basket member to hold; the first cross-sectional gate in
  this vault (vs. volatility-acceleration/-targeting's self-referential
  gates on the traded asset's own price series).
- [[signal-blending]] — average two structurally independent signals'
  position weights instead of gating one with the other; a gate can only
  ever remove exposure, a blend can add a second, differently-timed
  source of edge — the lever every prior gate in this vault lacked.
- [[low-volatility-anomaly]] — rank a basket by trailing realized
  volatility and hold the LEAST volatile subset, the opposite ranking
  direction from cross-sectional-momentum; a capital-constraint
  mispricing story (Betting Against Beta), not underreaction or a
  mechanical event — the first non-momentum, non-structure-break
  mechanism tested in this vault.
- [[pairs-trading-stat-arb]] — relative-value mean-reversion of the
  spread between two cointegrated assets, market-neutral by
  construction; structurally distinct from single-asset mean-reversion
  (which bets on one asset's own price level reverting) and the first
  long-short mechanism tested in this vault.

## Postmortems

- [[ms-shift-spy-example]] — worked-example paper review for
  ms-shift-spy-v1 (P9 template demonstration).
- [[research-campaign-2026-07-21]] — cross-strategy synthesis across all
  12 backtest-only strategies retired to date: all failed the 1.0/1.2
  gate; the two best, structurally unrelated mechanisms both land at
  0.813; every filter tried on tsmom-spy-qqq made it worse (3x); flags
  the threshold for human review via Telegram and proposes blending
  tsmom-spy-qqq with ms-shift-spy-high-displacement as the next untested
  lever. **2026-07-22 addendum:** `promotion_thresholds.toml` has exactly
  one commit ever (pre-dates every real backtest, no documented empirical
  basis); 13/13 real walk-forward results have now failed it; best is
  tsmom-ms-shift-blend (Sharpe 0.884, Sortino 1.297) — evidence laid out
  for human review, no replacement number proposed.
- [[blend-leg-search-2026-07-22]] — closes the 3rd-leg blend search:
  dual-momentum-equity-bond-gold (weaker standalone, higher correlation
  to tsmom via shared SPY logic) made the blend worse; tsmom-tlt-gld
  (weaker still standalone, near-zero correlation) made it the vault's
  best result (Sharpe 0.990). Reusable finding: correlation to existing
  legs, not standalone strength, is what determines whether a candidate
  leg helps. Documents the decision to stop at 3 legs rather than search
  for a 4th (no remaining low-correlation candidate in the pinned
  universe without a date-range mismatch or repeating dual-momentum's
  correlated outcome).
- [[pinned-universe-diversity-2026-07-22]] — investigates the
  universe-narrowness flag from sector-rotation/dual-momentum-equity-
  bond-gold: 14 of the 16 pinned symbols are all US-equity slices sharing
  one dominant factor (71.7% of variance, PC1; avg pairwise corr 0.685;
  broad index ETFs alone average 0.856); only TLT/GLD are genuine
  non-equity diversifiers; liquidity is not a constraint (all ≥$170M/day).
  Flag confirmed directionally correct but under-specified — real nominal
  breadth (10 labeled sectors), thin effective breadth (~3 PCA components
  carry non-redundant signal). No strategy re-run; diagnostic only.
- [[universe-scale-2026-07-22]] — closes the "genuinely larger universe"
  lever: cross-sectional-momentum-stocks50 (identical mechanism, 50
  single-name stocks instead of 10 sector ETFs) reproduced sector-
  rotation's Sharpe almost exactly (0.280 vs 0.255) despite passing the
  rotation-diversity falsification test far more cleanly (all 50 names
  used, no dominant single name), at ~5x the turnover and a reversed
  (degrading, not improving) OOS split. Universe size was not the
  limiting factor; the mechanism itself is. Argues against further
  universe-scaling investment on this mechanism.
- [[low-vol-anomaly-2026-07-22]] — first test of a mechanism outside
  momentum/structure-break/mean-reversion/calendar: low-vol-anomaly-
  stocks50 (Sharpe 0.518773) is the best cross-sectional result in this
  vault so far, but its own falsification check inverts the hypothesis —
  the low-vol-15 basket's raw Sharpe (0.5386) is below an equal-weight
  buy-and-hold benchmark of the same 50-stock universe (0.6608); vol
  fell 14.0% but return fell 31.5%, worse than a tautology. Composition
  (persistent defensive-sector cluster) rules out an implementation
  bug. Does not close the broader "new mechanism class" lever — only
  this one mechanism, on this sample.
- [[pairs-trading-stocks50-2026-07-22]] — closes the pairs-trading test:
  Sharpe -0.539613, this vault's first negative walk-forward result.
  Root cause isolated directly: the pre-registered Engle-Granger screen
  (p<0.05 full-sample) turned out to be spurious for all three traded
  pairs — re-running the same test on the first vs. second half of the
  identical sample shows none of them hold up in the second half
  (p=0.25-0.33), most likely shared long-run drift across a bull-biased
  9-year window rather than genuine short-horizon mean-reversion.
  Corroborated by the convergence-vs-timeout check: only 17.9-24.1% of
  trades actually converged, the rest rode to the max-hold safety exit.
  Reusable methodological finding: a full-sample-only cointegration
  screen is not sufficient evidence of tradeable mean-reversion; a
  stability-across-sub-periods check belongs in the *screening* step
  next time, not just as a post-hoc falsification check.
