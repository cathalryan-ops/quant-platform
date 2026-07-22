"""Pairs trading / statistical arbitrage on same-sector pairs from the
50-single-name-stock universe (see
brain/wiki/strategies/pairs-trading-stocks50.md).

First long-short mechanism in this vault: [[pairs-trading-stat-arb]] is
relative-value mean-reversion of the SPREAD between two cointegrated
assets, not absolute mean-reversion of either asset's own price level
(structurally distinct from mean_reversion_spy_qqq.py, already a
confirmed null). Three pairs, screened by Engle-Granger cointegration on
the full 2016-2024 window with a pre-registered p<0.05 threshold BEFORE
any backtest ran (see the wiki page for the full screen): JNJ/ABT
(p=0.0186), CVX/COP (p=0.0262), DUK/SO (p=0.0280) -- the three strongest
of four same-sector pairs that cleared the threshold (JPM/AXP at
p=0.0317 also cleared but was dropped for tractability, flagged as a
follow-up, not cherry-picked among failures).

Per pair, independently:
  1. Rolling hedge ratio beta_t = Cov(close_A, close_B) / Var(close_B)
     over `hedge_lookback` trading days ending at t (inclusive) --
     pandas' rolling .cov()/.var(), the standard OLS slope estimator,
     recomputed daily so the hedge ratio can drift with the relationship
     rather than being fit once over the whole sample (which would also
     leak the full-sample relationship into early-history decisions).
  2. Spread_t = close_A[t] - beta_t * close_B[t].
  3. z_t = (Spread_t - rolling_mean(Spread, zscore_lookback)_t) /
     rolling_std(Spread, zscore_lookback)_t, same window as the hedge
     ratio -- one rolling-window concept for the whole construction, not
     two independently chosen ones.
  4. Enter when flat and |z_t| crosses `entry_z`: z_t >= entry_z means the
     spread is rich -> short the spread (short A, long beta units of B);
     z_t <= -entry_z means the spread is cheap -> long the spread (long
     A, short beta units of B).
  5. Exit when |z_t| <= `exit_z` (converged) OR the position has been held
     `max_hold_days` sessions (safety exit against a relationship that
     stopped reverting) -- whichever comes first.

hedge_lookback = zscore_lookback = 60 trading days (~1 quarter): shorter
than every momentum lookback in this vault (252 days) by design -- this
is a relationship stat-arb needs to track responsively, not an annual
trend, and 60 sessions is inside the standard range used in the
practitioner pairs-trading literature (Gatev/Goetzmann/Rouwenhorst's
6-month trading period is the closest published analogue at this
horizon). entry_z=2.0 / exit_z=0.5 are the standard two-sigma-entry /
half-sigma-exit thresholds from the same literature. max_hold_days=20
(~1 trading month) is a safety exit, not a tuning target -- it only binds
when the spread stops reverting within a reasonable window. A max-hold
exit is re-arm-gated (`_pair_weights`'s `pending_reset`): the spread is
just as diverged the instant it fires, so an ungated re-entry would flip
right back in on the very next bar; a fresh entry for that pair is
blocked until |z| has actually dropped to <= exit_z at least once, the
same discipline `backtest/risk.py`'s stop-loss re-arm already established
for this vault (Option C).

Every rolling stat at day t uses only data through t inclusive (no future
row), the same lookahead convention as every other Signal in this vault
(e.g. low_vol_anomaly_stocks50.py's realized-vol rolling window) --
engine.py's own weights.shift(1) provides the additional T -> T+1
execution-timeline shift on top of this.

beta_t is clipped to `[beta_min, beta_max]` (default `[0.1, 3.0]`) purely
as a numerical-stability rail, not a tuning parameter: a `hedge_lookback`
rolling covariance/variance estimate can transiently spike on a short
window (e.g. right after a regime shift enters the window but hasn't
filled it yet), and an unclipped outlier would size the hedge leg
absurdly. The three chosen pairs' full-sample OLS betas are all 0.6-0.9
(checked directly before this was written), comfortably inside the
default clip range, so it is not expected to bind on the real backtest --
it exists as a safety rail against a noisy rolling estimate, not to
constrain the signal's normal operating range. The upper bound also
matches `backtest/signal.py`'s harness-enforced weight bound of `[-3,
3]`, so a clip-bound hedge leg can never itself trip that guard.
"""

from __future__ import annotations

import pandas as pd

DEFAULT_PAIRS: tuple[tuple[str, str], ...] = (
    ("JNJ", "ABT"),
    ("CVX", "COP"),
    ("DUK", "SO"),
)


class Signal:
    def __init__(
        self,
        pairs: tuple[tuple[str, str], ...] = DEFAULT_PAIRS,
        hedge_lookback: int = 60,
        zscore_lookback: int = 60,
        entry_z: float = 2.0,
        exit_z: float = 0.5,
        max_hold_days: int = 20,
        beta_min: float = 0.1,
        beta_max: float = 3.0,
    ) -> None:
        if hedge_lookback < 2:
            raise ValueError("hedge_lookback must be >= 2")
        if zscore_lookback < 2:
            raise ValueError("zscore_lookback must be >= 2")
        if exit_z < 0:
            raise ValueError("exit_z must be >= 0")
        if entry_z <= exit_z:
            raise ValueError("entry_z must be > exit_z")
        if max_hold_days < 1:
            raise ValueError("max_hold_days must be >= 1")
        if not (0 < beta_min < beta_max):
            raise ValueError("must have 0 < beta_min < beta_max")
        self.pairs = tuple(pairs)
        self.hedge_lookback = hedge_lookback
        self.zscore_lookback = zscore_lookback
        self.entry_z = entry_z
        self.exit_z = exit_z
        self.max_hold_days = max_hold_days
        self.beta_min = beta_min
        self.beta_max = beta_max

    def generate(self, bars) -> pd.DataFrame:
        close = bars.close
        symbols = list(bars.columns)
        weights = pd.DataFrame(0.0, index=bars.index, columns=symbols)

        for sym_a, sym_b in self.pairs:
            beta = close[sym_a].rolling(self.hedge_lookback).cov(close[sym_b]) / (
                close[sym_b].rolling(self.hedge_lookback).var()
            )
            beta = beta.clip(lower=self.beta_min, upper=self.beta_max)
            spread = close[sym_a] - beta * close[sym_b]
            mean = spread.rolling(self.zscore_lookback).mean()
            std = spread.rolling(self.zscore_lookback).std()
            z = (spread - mean) / std

            wa, wb = _pair_weights(
                z.to_numpy(dtype=float),
                beta.to_numpy(dtype=float),
                self.entry_z,
                self.exit_z,
                self.max_hold_days,
            )
            weights[sym_a] = wa
            weights[sym_b] = wb

        return weights[bars.columns]

    def export_params(self) -> dict:
        return {
            "type": "pairs_trading",
            "pairs": [list(p) for p in self.pairs],
            "hedge_lookback": self.hedge_lookback,
            "zscore_lookback": self.zscore_lookback,
            "entry_z": self.entry_z,
            "exit_z": self.exit_z,
            "max_hold_days": self.max_hold_days,
            "beta_min": self.beta_min,
            "beta_max": self.beta_max,
        }


def _pair_weights(
    z: list[float],
    beta: list[float],
    entry_z: float,
    exit_z: float,
    max_hold_days: int,
) -> tuple[list[float], list[float]]:
    """State machine over a single pair's z-score/beta series. Returns
    (weight_A, weight_B) arrays. `state`: 0 = flat, +1 = long the spread
    (long A, short beta*B), -1 = short the spread (short A, long beta*B).
    NaN z/beta (not enough rolling history yet) forces flat.

    An exit via genuine convergence (|z| <= exit_z) means the spread has
    actually reverted -- a fresh entry is honored immediately. An exit via
    `max_hold_days` (the spread never converged) sets `pending_reset`:
    since the spread is still just as diverged the instant it fires, an
    ungated re-entry would flip right back in on the very next bar and the
    safety exit would do nothing. A new entry for this pair is blocked
    until |z| has actually dropped to <= exit_z at least once -- the same
    "must see real convergence before trusting the signal again" gate
    `backtest/risk.py`'s stop-loss re-arm uses, adapted to this state
    machine's own exit condition rather than a price reclaim."""
    n = len(z)
    wa = [0.0] * n
    wb = [0.0] * n
    state = 0
    hold = 0
    pending_reset = False

    for t in range(n):
        zt = z[t]
        bt = beta[t]
        valid = zt == zt and bt == bt  # not NaN

        if pending_reset and valid and abs(zt) <= exit_z:
            pending_reset = False

        if state == 0:
            if not pending_reset and valid and zt >= entry_z:
                state = -1
                hold = 0
            elif not pending_reset and valid and zt <= -entry_z:
                state = 1
                hold = 0
        else:
            hold += 1
            if not valid or abs(zt) <= exit_z:
                state = 0
                hold = 0
            elif hold >= max_hold_days:
                state = 0
                hold = 0
                pending_reset = True

        if state == 1:
            wa[t] = 1.0
            wb[t] = -bt
        elif state == -1:
            wa[t] = -1.0
            wb[t] = bt
        else:
            wa[t] = 0.0
            wb[t] = 0.0

    return wa, wb
