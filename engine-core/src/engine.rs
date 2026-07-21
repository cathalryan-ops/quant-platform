//! Engine-side types shared by the paper and live engines: orders, fills,
//! portfolio state, the parameterised ruleset interpreter (ADR 0002), and
//! the append-only state journal that makes restarts lossless.

use std::collections::{BTreeMap, VecDeque};
use std::fs::OpenOptions;
use std::io::{BufRead, BufReader, Write};
use std::path::Path;

use serde::{Deserialize, Serialize};

use crate::contracts::DataSnapshot;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Side {
    Buy,
    Sell,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Order {
    /// Idempotent client order id: deterministic function of
    /// strategy id + symbol + trading day (P8 requirement, shared here).
    pub client_order_id: String,
    pub strategy_id: String,
    pub symbol: String,
    pub side: Side,
    pub qty: f64,
    /// Trading day (YYYY-MM-DD) the decision belongs to.
    pub date: String,
}

impl Order {
    pub fn client_order_id(strategy_id: &str, symbol: &str, date: &str) -> String {
        format!("{strategy_id}--{symbol}--{date}")
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Fill {
    pub client_order_id: String,
    pub symbol: String,
    pub side: Side,
    pub qty: f64,
    pub price: f64,
    pub fees: f64,
    pub date: String,
}

/// A daily OHLCV bar as delivered by a feed.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Bar {
    pub symbol: String,
    /// YYYY-MM-DD session date.
    pub date: String,
    pub open: f64,
    pub high: f64,
    pub low: f64,
    pub close: f64,
    pub volume: f64,
}

/// Full portfolio state; snapshotted to the journal after every processed
/// session so a restart resumes exactly where it left off.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct PortfolioState {
    pub cash: f64,
    /// symbol -> signed quantity (v1 is long-only, so >= 0).
    pub positions: BTreeMap<String, f64>,
    /// symbol -> rolling OHLC window (bounded by the ruleset's history window).
    /// Full bars, not just closes, so price-action rulesets (swings, ranges)
    /// can be interpreted.
    pub bars: BTreeMap<String, VecDeque<Bar>>,
    /// First and last fully processed session dates (restart resume + result period).
    pub first_date: Option<String>,
    pub last_date: Option<String>,
    /// Cumulative fill count (num_trades in results).
    pub fills: u32,
    /// Equity value at the end of each processed session.
    pub equity_curve: Vec<f64>,
    /// symbol -> stop-loss overlay tracking state (manifest `risk.stop_loss_pct`).
    /// `#[serde(default)]` so journals written before this field existed still
    /// load cleanly on restart — a missing entry means "flat, never entered",
    /// the correct default for a symbol that hasn't been seen by the overlay.
    #[serde(default)]
    pub stop_loss: BTreeMap<String, StopLossState>,
}

impl PortfolioState {
    pub fn new(cash: f64) -> Self {
        Self {
            cash,
            positions: BTreeMap::new(),
            bars: BTreeMap::new(),
            first_date: None,
            last_date: None,
            fills: 0,
            equity_curve: Vec::new(),
            stop_loss: BTreeMap::new(),
        }
    }

    pub fn equity(&self, last_close: &BTreeMap<String, f64>) -> f64 {
        self.cash
            + self
                .positions
                .iter()
                .map(|(s, qty)| qty * last_close.get(s).copied().unwrap_or(0.0))
                .sum::<f64>()
    }

    /// Run one symbol's raw target weight through its stop-loss overlay for
    /// this session, advancing (and persisting, via this `PortfolioState`)
    /// that symbol's stop-tracking state. See `StopLossState::apply` for the
    /// exact semantics. Must be called at most once per symbol per session,
    /// every session — the overlay's re-arm/transition detection depends on
    /// seeing each session's raw weight in order.
    pub fn apply_stop_loss(
        &mut self,
        symbol: &str,
        raw_weight: f64,
        close: f64,
        low: f64,
        stop_loss_pct: f64,
        cooldown_sessions: u32,
    ) -> Result<f64, String> {
        self.stop_loss.entry(symbol.to_string()).or_default().apply(
            raw_weight,
            close,
            low,
            stop_loss_pct,
            cooldown_sessions,
        )
    }
}

/// Per-symbol stop-loss overlay tracking state for the manifest-declared
/// `risk.stop_loss_pct` control. Persisted inside `PortfolioState` (and thus
/// the journal) so a restart never loses "stopped, awaiting re-arm" status —
/// the same restart-safety invariant the rest of the portfolio state has.
///
/// Session-by-session mirror of `apply_stop_loss` in
/// `sandbox/backtest/backtest/risk.py` (which operates vectorised over a
/// whole price history instead of one session at a time); see that
/// function's docstring for the full rationale. Kept out of
/// `Ruleset::target_weight` deliberately, same reasoning as the Python side:
/// it's a risk-control overlay on top of the signal's raw decision, not part
/// of the signal itself.
#[derive(Debug, Clone, Copy, PartialEq, Default, Serialize, Deserialize)]
pub struct StopLossState {
    /// Currently holding a position for this symbol, as tracked by this
    /// overlay (independent of whether the raw signal still says long).
    in_position: bool,
    /// True once stopped out; forces flat regardless of the raw signal until
    /// re-armed (see `apply`'s Re-arm section).
    stopped: bool,
    /// Entry fill price recorded on the day this symbol's raw weight last
    /// transitioned from 0 to >0 while not stopped. Retained (not reset)
    /// after a stop so a later price-reclaim re-arm has something to compare
    /// against.
    entry_price: f64,
    /// Previous session's raw (pre-overlay) weight; used to detect a fresh
    /// 0 -> >0 transition for entry / re-arm.
    prev_raw: f64,
    /// Sessions remaining before a price-reclaim re-arm becomes eligible.
    /// Set to `cooldown_sessions` on each stop-out; decremented each session
    /// while stopped. Absent in a pre-Option-C journal => 0 via `#[serde(default)]`.
    #[serde(default)]
    cooldown_remaining: u32,
}

impl StopLossState {
    /// Apply the stop-loss overlay for one symbol on one session.
    ///
    /// `raw_weight` is `Ruleset::target_weight`'s output for this session,
    /// before any risk overlay. `close`/`low` are that session's bar prices
    /// (fills happen at/near the session close in this platform's daily-bar
    /// model, so `close` doubles as the fill price for entry-price purposes).
    /// Returns the weight to actually use for sizing this session — either
    /// `raw_weight` unchanged, or 0.0 if stopped/flat.
    ///
    /// Semantics (must match `backtest/risk.py::apply_stop_loss` exactly):
    /// - Entry: the first session a symbol's raw weight is > 0 after being
    ///   0. Entry price is that session's `close`.
    /// - The stop check does not run on the entry session itself — only from
    ///   the following session onward (you can't be stopped out before
    ///   you've filled; the entry price is only known after that session's
    ///   low has already occurred).
    /// - Trigger: once in position, if a later session's `low` breaches
    ///   `entry_price * (1 - stop_loss_pct/100)`, the position is forced
    ///   flat from that session onward, and a `cooldown_sessions`-session
    ///   countdown starts.
    /// - Re-arm (Option C, combined): once stopped out, stays forced flat
    ///   until EITHER of these fires, whichever comes first. (A) the raw
    ///   signal produces a FRESH 0 -> >0 transition — the original safety
    ///   property, ungated by cooldown (already rare, nothing to protect
    ///   against here). (B) `cooldown_sessions` have elapsed since the stop
    ///   AND this session's close reclaims (>=) `entry_price` — bounds how
    ///   long a slow-to-reverse trend-following signal can leave the
    ///   position locked out through a recovery the raw signal itself would
    ///   have ridden. `cooldown_sessions=0` means (B) is live starting the
    ///   very next session.
    pub fn apply(
        &mut self,
        raw_weight: f64,
        close: f64,
        low: f64,
        stop_loss_pct: f64,
        cooldown_sessions: u32,
    ) -> Result<f64, String> {
        if stop_loss_pct <= 0.0 {
            return Err(format!("stop_loss_pct must be > 0, got {stop_loss_pct}"));
        }

        if self.stopped {
            if self.cooldown_remaining > 0 {
                self.cooldown_remaining -= 1;
            }
            let fresh_entry = self.prev_raw == 0.0 && raw_weight > 0.0;
            let price_reclaimed = self.cooldown_remaining == 0 && close >= self.entry_price;
            if fresh_entry || price_reclaimed {
                self.stopped = false; // (A) or (B) — whichever fired first
            }
        }

        let result = if raw_weight > 0.0 && !self.stopped {
            if !self.in_position {
                self.entry_price = close;
                self.in_position = true;
                raw_weight // entry session: no stop check possible yet
            } else if low <= self.entry_price * (1.0 - stop_loss_pct / 100.0) {
                self.in_position = false;
                self.stopped = true;
                self.cooldown_remaining = cooldown_sessions;
                0.0
            } else {
                raw_weight
            }
        } else {
            self.in_position = false;
            0.0
        };

        self.prev_raw = raw_weight;
        Ok(result)
    }
}

/// Fitted signal parameters exported by the backtest stage (ADR 0002).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Ruleset {
    pub schema_version: String,
    pub strategy_id: String,
    pub family: String,
    pub max_position_pct: f64,
    pub params: RulesetParams,
    pub data_snapshot: DataSnapshot,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case", deny_unknown_fields)]
pub enum RulesetParams {
    SmaCross {
        fast: usize,
        slow: usize,
    },
    /// Market-structure shift + displacement (mirrors
    /// sandbox/backtest/strategies/ms_shift_spy.py; golden-tested).
    MsShift {
        swing_lookback: usize,
        atr_period: usize,
        displacement_mult: f64,
    },
}

impl Ruleset {
    pub fn load(path: &Path) -> Result<Self, String> {
        let raw = std::fs::read_to_string(path).map_err(|e| format!("read {path:?}: {e}"))?;
        serde_json::from_str(&raw).map_err(|e| format!("parse {path:?}: {e}"))
    }

    /// Bars of history the engine retains for this ruleset. It must be large
    /// enough that the interpreter can re-derive its state from the window
    /// alone. `ms_shift` is stateful (trend persists between shifts), so it
    /// keeps a generous window — a position held longer than this with no
    /// intervening shift is not expected at daily/swing cadence (ADR 0002).
    pub fn history_window(&self) -> usize {
        match self.params {
            RulesetParams::SmaCross { slow, .. } => slow * 2,
            RulesetParams::MsShift { .. } => 400,
        }
    }

    /// Target long weight in [0, 1] for one symbol given its OHLC window
    /// (oldest first, current session's bar last). Mirrors the Python Signal
    /// semantics exactly; golden-tested against the harness.
    pub fn target_weight(&self, bars: &VecDeque<Bar>) -> f64 {
        match self.params {
            RulesetParams::SmaCross { fast, slow } => {
                if bars.len() < slow {
                    return 0.0;
                }
                let mean_last = |n: usize| -> f64 {
                    bars.iter().rev().take(n).map(|b| b.close).sum::<f64>() / n as f64
                };
                if mean_last(fast) > mean_last(slow) {
                    1.0
                } else {
                    0.0
                }
            }
            RulesetParams::MsShift {
                swing_lookback,
                atr_period,
                displacement_mult,
            } => ms_shift_weight(bars, swing_lookback, atr_period, displacement_mult),
        }
    }
}

/// Simple mean of the last `period` true ranges ending at t, or None if there
/// is not enough history. Ascending accumulation order matches the Python
/// implementation so the boundary comparisons agree bit-for-bit.
fn atr_at(high: &[f64], low: &[f64], close: &[f64], t: usize, period: usize) -> Option<f64> {
    if t < period {
        return None;
    }
    let mut total = 0.0;
    for i in (t - period + 1)..=t {
        let tr_hl = high[i] - low[i];
        let tr_hc = (high[i] - close[i - 1]).abs();
        let tr_lc = (low[i] - close[i - 1]).abs();
        total += tr_hl.max(tr_hc).max(tr_lc);
    }
    Some(total / period as f64)
}

fn is_swing_high(high: &[f64], i: usize, k: usize) -> bool {
    if i < k || i + k >= high.len() {
        return false;
    }
    (i - k..=i + k).all(|j| j == i || high[i] > high[j])
}

fn is_swing_low(low: &[f64], i: usize, k: usize) -> bool {
    if i < k || i + k >= low.len() {
        return false;
    }
    (i - k..=i + k).all(|j| j == i || low[i] < low[j])
}

/// Causal MS-shift trend at the latest bar of `bars` (recomputed from flat
/// over the window). Byte-for-byte mirror of `_weights` in ms_shift_spy.py.
fn ms_shift_weight(bars: &VecDeque<Bar>, k: usize, period: usize, mult: f64) -> f64 {
    let n = bars.len();
    let high: Vec<f64> = bars.iter().map(|b| b.high).collect();
    let low: Vec<f64> = bars.iter().map(|b| b.low).collect();
    let close: Vec<f64> = bars.iter().map(|b| b.close).collect();

    let mut trend = 0.0;
    let mut last_swing_high: Option<f64> = None;
    let mut last_swing_low: Option<f64> = None;
    for t in 0..n {
        // Confirm the swing centred on t-k (window [t-2k, t], all <= t).
        if t >= k {
            let c = t - k;
            if is_swing_high(&high, c, k) {
                last_swing_high = Some(high[c]);
            }
            if is_swing_low(&low, c, k) {
                last_swing_low = Some(low[c]);
            }
        }
        if let Some(atr) = atr_at(&high, &low, &close, t, period) {
            if atr > 0.0 {
                let displaced = (high[t] - low[t]) >= mult * atr;
                if displaced && last_swing_high.is_some_and(|sh| close[t] > sh) {
                    trend = 1.0;
                } else if displaced && last_swing_low.is_some_and(|sl| close[t] < sl) {
                    trend = 0.0;
                }
            }
        }
    }
    trend
}

/// Append-only JSONL state journal. One `PortfolioState` snapshot per
/// processed session; recovery = last line. Never truncated.
pub struct Journal;

impl Journal {
    pub fn append(path: &Path, state: &PortfolioState) -> std::io::Result<()> {
        if let Some(parent) = path.parent() {
            std::fs::create_dir_all(parent)?;
        }
        let mut f = OpenOptions::new().create(true).append(true).open(path)?;
        writeln!(
            f,
            "{}",
            serde_json::to_string(state).expect("state serializes")
        )?;
        f.sync_all()
    }

    pub fn load_last(path: &Path) -> std::io::Result<Option<PortfolioState>> {
        if !path.exists() {
            return Ok(None);
        }
        let reader = BufReader::new(std::fs::File::open(path)?);
        let mut last = None;
        for line in reader.lines() {
            let line = line?;
            if line.trim().is_empty() {
                continue;
            }
            last = Some(serde_json::from_str(&line).map_err(std::io::Error::other)?);
        }
        Ok(last)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn ruleset() -> Ruleset {
        serde_json::from_value(serde_json::json!({
            "schema_version": "1.0.0",
            "strategy_id": "sma-cross-test-v1",
            "family": "swing",
            "max_position_pct": 5.0,
            "params": {"type": "sma_cross", "fast": 2, "slow": 3},
            "data_snapshot": {
                "parquet_path": "data/x.parquet",
                "content_hash": "sha256:9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
                "source_feed": "synthetic_test",
                "period": {"start": "2020-01-01", "end": "2020-12-31"}
            }
        }))
        .unwrap()
    }

    fn bar_at(px: f64) -> Bar {
        Bar {
            symbol: "SPY".into(),
            date: "2020-01-01".into(),
            open: px,
            high: px,
            low: px,
            close: px,
            volume: 1.0,
        }
    }

    fn window(prices: &[f64]) -> VecDeque<Bar> {
        prices.iter().map(|&p| bar_at(p)).collect()
    }

    #[test]
    fn sma_cross_weight_matches_python_semantics() {
        let r = ruleset();
        assert_eq!(r.target_weight(&window(&[1.0, 2.0, 3.0])), 1.0); // fast 2.5 > slow 2.0
        assert_eq!(r.target_weight(&window(&[3.0, 2.0, 1.0])), 0.0);
        assert_eq!(r.target_weight(&window(&[1.0, 2.0])), 0.0); // not enough history
    }

    #[test]
    fn journal_roundtrip_returns_last_snapshot() {
        let dir = std::env::temp_dir().join(format!("qp-journal-{}", std::process::id()));
        let path = dir.join("journal.jsonl");
        let mut s = PortfolioState::new(100_000.0);
        Journal::append(&path, &s).unwrap();
        s.cash = 99_000.0;
        s.last_date = Some("2020-01-02".into());
        Journal::append(&path, &s).unwrap();
        assert_eq!(Journal::load_last(&path).unwrap().unwrap(), s);
        std::fs::remove_dir_all(dir).ok();
    }

    // ---- StopLossState: mirrors sandbox/backtest/tests/test_risk.py ----

    /// Run a full (weight, close, low) session series through a fresh
    /// `StopLossState`, session by session, exactly as the engines call it
    /// once per symbol per session. Returns the resulting weight sequence.
    fn run_stop_loss(weights: &[f64], close: &[f64], low: &[f64], stop_loss_pct: f64) -> Vec<f64> {
        run_stop_loss_cooldown(weights, close, low, stop_loss_pct, 0)
    }

    fn run_stop_loss_cooldown(
        weights: &[f64],
        close: &[f64],
        low: &[f64],
        stop_loss_pct: f64,
        cooldown_sessions: u32,
    ) -> Vec<f64> {
        let mut s = StopLossState::default();
        weights
            .iter()
            .zip(close)
            .zip(low)
            .map(|((&w, &c), &l)| s.apply(w, c, l, stop_loss_pct, cooldown_sessions).unwrap())
            .collect()
    }

    #[test]
    fn no_stop_hit_passes_weights_through_unchanged() {
        let weights = [0.0, 1.0, 1.0, 1.0, 0.0];
        let close = [100.0, 101.0, 102.0, 103.0, 103.0];
        let low = [99.0, 100.5, 101.5, 102.5, 102.0]; // never breaches a 2% stop
        assert_eq!(
            run_stop_loss(&weights, &close, &low, 2.0),
            vec![0.0, 1.0, 1.0, 1.0, 0.0]
        );
    }

    #[test]
    fn stop_triggers_and_forces_flat() {
        // Entry at session 1 (close=100). Session 2's low (97) breaches
        // 100*(1-0.02)=98.
        let weights = [0.0, 1.0, 1.0, 1.0, 1.0];
        let close = [99.0, 100.0, 96.0, 95.0, 94.0];
        let low = [98.0, 99.5, 97.0, 94.0, 93.0];
        assert_eq!(
            run_stop_loss(&weights, &close, &low, 2.0),
            vec![0.0, 1.0, 0.0, 0.0, 0.0]
        );
    }

    #[test]
    fn entry_day_itself_is_never_stopped_out() {
        // Entry session's own low (way below its own close) must not trigger
        // a stop — the check starts the session AFTER entry, matching the
        // close-fill convention (you can't be stopped out before you fill).
        let weights = [0.0, 1.0, 0.0];
        let close = [100.0, 100.0, 100.0];
        let low = [100.0, 50.0, 100.0]; // entry day's low is deeply below entry price
        assert_eq!(
            run_stop_loss(&weights, &close, &low, 2.0),
            vec![0.0, 1.0, 0.0]
        );
    }

    #[test]
    fn stopped_position_does_not_reenter_until_fresh_signal() {
        // Stopped out on session 2; raw signal stays 1 through session 4 —
        // must stay flat until the raw signal drops to 0 and rises again
        // (session 6).
        let weights = [0.0, 1.0, 1.0, 1.0, 1.0, 0.0, 1.0];
        let close = [100.0, 100.0, 96.0, 96.0, 96.0, 96.0, 96.0];
        let low = [99.0, 99.0, 97.0, 99.0, 99.0, 95.0, 95.5];
        assert_eq!(
            run_stop_loss(&weights, &close, &low, 2.0),
            //             0     1     2     3     4     5     6
            vec![0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0]
        );
    }

    #[test]
    fn symbols_are_independent() {
        let mut state = PortfolioState::new(100_000.0);
        // SPY: stops out on session 2 (index 2). QQQ: never stops.
        let spy_close = [100.0, 100.0, 100.0];
        let spy_low = [99.0, 99.0, 90.0];
        let qqq_close = [200.0, 200.0, 200.0];
        let qqq_low = [199.0, 199.0, 199.0];
        let weights = [0.0, 1.0, 1.0];

        let mut spy_out = Vec::new();
        let mut qqq_out = Vec::new();
        for t in 0..3 {
            spy_out.push(
                state
                    .apply_stop_loss("SPY", weights[t], spy_close[t], spy_low[t], 2.0, 0)
                    .unwrap(),
            );
            qqq_out.push(
                state
                    .apply_stop_loss("QQQ", weights[t], qqq_close[t], qqq_low[t], 2.0, 0)
                    .unwrap(),
            );
        }
        assert_eq!(spy_out, vec![0.0, 1.0, 0.0]);
        assert_eq!(qqq_out, vec![0.0, 1.0, 1.0]);
    }

    #[test]
    fn invalid_stop_loss_pct_is_rejected() {
        let mut s = StopLossState::default();
        assert!(s.apply(1.0, 100.0, 99.0, 0.0, 0).is_err());
        assert!(s.apply(1.0, 100.0, 99.0, -1.0, 0).is_err());
    }

    #[test]
    fn stop_loss_state_survives_journal_roundtrip() {
        // Restart-safety: a "stopped, awaiting re-arm" symbol must resume
        // exactly, and a journal written before this field existed (no
        // `stop_loss` key at all) must still load via #[serde(default)].
        let dir = std::env::temp_dir().join(format!("qp-stoploss-journal-{}", std::process::id()));
        let path = dir.join("journal.jsonl");

        let mut legacy = serde_json::to_value(PortfolioState::new(100_000.0)).unwrap();
        legacy.as_object_mut().unwrap().remove("stop_loss");
        std::fs::create_dir_all(&dir).unwrap();
        std::fs::write(&path, format!("{legacy}\n")).unwrap();
        let loaded = Journal::load_last(&path).unwrap().unwrap();
        assert!(
            loaded.stop_loss.is_empty(),
            "missing field defaults to empty map"
        );

        let mut s = PortfolioState::new(100_000.0);
        s.apply_stop_loss("SPY", 1.0, 100.0, 99.0, 2.0, 0).unwrap(); // entry
        s.apply_stop_loss("SPY", 1.0, 96.0, 90.0, 2.0, 0).unwrap(); // stopped out
        Journal::append(&path, &s).unwrap();
        let resumed = Journal::load_last(&path).unwrap().unwrap();
        assert_eq!(resumed, s);
        // The resumed state must still refuse to re-enter without a fresh
        // 0 -> >0 transition of the raw signal (re-arm behaviour survives).
        // close=96 < entry_price=100, so the (B) price-reclaim path doesn't
        // fire either — genuinely still stopped, not just cooldown-gated.
        let mut resumed = resumed;
        assert_eq!(
            resumed
                .apply_stop_loss("SPY", 1.0, 96.0, 96.0, 2.0, 0)
                .unwrap(),
            0.0,
            "still stopped after restart — raw signal never dropped to 0, price never reclaimed"
        );
        std::fs::remove_dir_all(dir).ok();
    }

    #[test]
    fn cooldown_remaining_defaults_on_pre_option_c_journal() {
        // A journal written by the original stop-loss shipment (before
        // Option C) has a `stop_loss` map whose per-symbol state has no
        // `cooldown_remaining` key at all — must still load, defaulting to 0.
        let dir = std::env::temp_dir().join(format!("qp-cooldown-journal-{}", std::process::id()));
        let path = dir.join("journal.jsonl");
        std::fs::create_dir_all(&dir).unwrap();

        let mut legacy = serde_json::to_value(PortfolioState::new(100_000.0)).unwrap();
        legacy["stop_loss"]["SPY"] = serde_json::json!({
            "in_position": false,
            "stopped": true,
            "entry_price": 100.0,
            "prev_raw": 1.0
        });
        std::fs::write(&path, format!("{legacy}\n")).unwrap();
        let loaded = Journal::load_last(&path).unwrap().unwrap();
        assert_eq!(loaded.stop_loss["SPY"].cooldown_remaining, 0);
    }

    // --- Option C: combined re-arm (fresh raw transition OR post-cooldown
    // price reclaim, whichever fires first) — mirrors
    // sandbox/backtest/tests/test_risk.py exactly. ---

    #[test]
    fn price_reclaim_rearms_even_though_raw_signal_never_drops_to_zero() {
        let weights = [0.0, 1.0, 1.0, 1.0, 1.0, 1.0];
        let close = [100.0, 100.0, 90.0, 85.0, 90.0, 101.0];
        let low = [99.0, 99.0, 88.0, 84.0, 89.0, 100.0];
        assert_eq!(
            run_stop_loss_cooldown(&weights, &close, &low, 2.0, 1),
            //                       0     1     2     3     4     5
            vec![0.0, 1.0, 0.0, 0.0, 0.0, 1.0]
        );
    }

    #[test]
    fn price_reclaim_is_gated_by_cooldown() {
        let weights = [0.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0];
        let close = [100.0, 100.0, 90.0, 101.0, 101.0, 101.0, 101.0];
        let low = [99.0, 99.0, 88.0, 100.0, 100.0, 100.0, 100.0];
        assert_eq!(
            run_stop_loss_cooldown(&weights, &close, &low, 2.0, 3),
            //                       0     1     2     3     4     5     6
            vec![0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 1.0]
        );
    }

    #[test]
    fn fresh_transition_rearm_ignores_cooldown() {
        let weights = [0.0, 1.0, 1.0, 0.0, 1.0];
        let close = [100.0, 100.0, 90.0, 90.0, 90.0];
        let low = [99.0, 99.0, 88.0, 89.0, 89.0];
        assert_eq!(
            run_stop_loss_cooldown(&weights, &close, &low, 2.0, 10),
            //                       0     1     2     3     4
            vec![0.0, 1.0, 0.0, 0.0, 1.0]
        );
    }
}
