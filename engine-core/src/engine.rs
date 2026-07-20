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
}
