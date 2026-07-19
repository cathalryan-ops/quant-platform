//! Market-data feeds. A feed yields one completed session at a time (one
//! daily bar per universe symbol). Enum dispatch keeps the trait dyn-free.

use engine_core::engine::Bar;

use crate::alpaca::AlpacaFeed;

pub enum AnyFeed {
    Sim(SimFeed),
    Alpaca(Box<AlpacaFeed>),
    /// Pre-scripted sessions, for tests that need exact price paths
    /// (e.g. crafting a crash to trip the circuit breaker).
    Script(std::vec::IntoIter<Vec<Bar>>),
}

impl AnyFeed {
    /// Next completed session's bars, or None when the feed is exhausted.
    pub async fn next_session(&mut self) -> Result<Option<Vec<Bar>>, String> {
        match self {
            AnyFeed::Sim(f) => Ok(f.next_session()),
            AnyFeed::Alpaca(f) => f.next_session().await,
            AnyFeed::Script(iter) => Ok(iter.next()),
        }
    }
}

/// Deterministic synthetic feed (seeded xorshift random walk) for tests and
/// offline runs. Same seed => identical sessions, which is what makes the
/// restart-resume test meaningful.
pub struct SimFeed {
    universe: Vec<String>,
    remaining: usize,
    day: usize,
    prices: Vec<f64>,
    rng_state: u64,
}

impl SimFeed {
    pub fn new(universe: Vec<String>, sessions: usize, seed: u64) -> Self {
        let prices = (0..universe.len())
            .map(|i| 100.0 * (i + 1) as f64)
            .collect();
        Self {
            universe,
            remaining: sessions,
            day: 0,
            prices,
            rng_state: seed.max(1),
        }
    }

    fn next_f64(&mut self) -> f64 {
        // xorshift64* — deterministic, dependency-free.
        let mut x = self.rng_state;
        x ^= x >> 12;
        x ^= x << 25;
        x ^= x >> 27;
        self.rng_state = x;
        (x.wrapping_mul(0x2545F4914F6CDD1D) >> 11) as f64 / (1u64 << 53) as f64
    }

    fn next_session(&mut self) -> Option<Vec<Bar>> {
        if self.remaining == 0 {
            return None;
        }
        self.remaining -= 1;
        self.day += 1;
        // Synthetic calendar: sequential dates from 2030-01-01 (weekends ignored).
        let date = chrono::NaiveDate::from_ymd_opt(2030, 1, 1)
            .unwrap()
            .checked_add_days(chrono::Days::new(self.day as u64))
            .unwrap()
            .format("%Y-%m-%d")
            .to_string();
        let mut bars = Vec::with_capacity(self.universe.len());
        for i in 0..self.universe.len() {
            let ret = (self.next_f64() - 0.5) * 0.02 + 0.0004;
            self.prices[i] *= 1.0 + ret;
            let c = self.prices[i];
            bars.push(Bar {
                symbol: self.universe[i].clone(),
                date: date.clone(),
                open: c * 0.999,
                high: c * 1.005,
                low: c * 0.995,
                close: c,
                volume: 1_000_000.0,
            });
        }
        Some(bars)
    }
}
