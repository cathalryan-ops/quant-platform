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
    /// symbol -> rolling close window (bounded by the ruleset's lookback).
    pub closes: BTreeMap<String, VecDeque<f64>>,
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
            closes: BTreeMap::new(),
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
    SmaCross { fast: usize, slow: usize },
}

impl Ruleset {
    pub fn load(path: &Path) -> Result<Self, String> {
        let raw = std::fs::read_to_string(path).map_err(|e| format!("read {path:?}: {e}"))?;
        serde_json::from_str(&raw).map_err(|e| format!("parse {path:?}: {e}"))
    }

    /// Bars of history the interpreter needs before it can emit a weight.
    pub fn lookback(&self) -> usize {
        match self.params {
            RulesetParams::SmaCross { slow, .. } => slow,
        }
    }

    /// Target long weight in [0, 1] for one symbol given its close window
    /// (oldest first, current session's close last). Mirrors the Python
    /// Signal semantics exactly; golden-tested against the harness.
    pub fn target_weight(&self, closes: &VecDeque<f64>) -> f64 {
        match self.params {
            RulesetParams::SmaCross { fast, slow } => {
                if closes.len() < slow {
                    return 0.0;
                }
                let mean_last =
                    |n: usize| -> f64 { closes.iter().rev().take(n).sum::<f64>() / n as f64 };
                if mean_last(fast) > mean_last(slow) {
                    1.0
                } else {
                    0.0
                }
            }
        }
    }
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

    #[test]
    fn sma_cross_weight_matches_python_semantics() {
        let r = ruleset();
        let rising: VecDeque<f64> = [1.0, 2.0, 3.0].into_iter().collect();
        let falling: VecDeque<f64> = [3.0, 2.0, 1.0].into_iter().collect();
        let short: VecDeque<f64> = [1.0, 2.0].into_iter().collect();
        assert_eq!(r.target_weight(&rising), 1.0); // fast SMA 2.5 > slow SMA 2.0
        assert_eq!(r.target_weight(&falling), 0.0);
        assert_eq!(r.target_weight(&short), 0.0); // not enough history
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
