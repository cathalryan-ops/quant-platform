//! Broker abstraction. Sim fills locally (offline tests); Alpaca targets the
//! paper-trading endpoint in dry-run (the default) and the live endpoint only
//! behind the triple gate (env var + CLI flag + guardrails environment).

use std::collections::BTreeMap;

use engine_core::engine::{Fill, Order, Side};

pub const ALPACA_PAPER: &str = "https://paper-api.alpaca.markets";
pub const ALPACA_LIVE: &str = "https://api.alpaca.markets";

pub enum Broker {
    /// Local simulated fills at the provided reference price + slippage.
    Sim {
        slippage_bps: f64,
    },
    Alpaca(Box<AlpacaBroker>),
}

impl Broker {
    /// Submit with an idempotent client order id. `ref_price` is the latest
    /// close, used for sim fills and for marketable-limit pricing.
    pub async fn submit(&mut self, order: &Order, ref_price: f64) -> Result<Fill, String> {
        match self {
            Broker::Sim { slippage_bps } => {
                let sign = if order.side == Side::Buy { 1.0 } else { -1.0 };
                let price = ref_price * (1.0 + sign * *slippage_bps / 10_000.0);
                Ok(Fill {
                    client_order_id: order.client_order_id.clone(),
                    symbol: order.symbol.clone(),
                    side: order.side,
                    qty: order.qty,
                    price,
                    fees: order.qty.abs() * price * 0.0005,
                    date: order.date.clone(),
                })
            }
            Broker::Alpaca(b) => b.submit(order).await,
        }
    }

    /// Broker-side positions (symbol -> qty) for startup reconciliation.
    /// The broker's ledger is the truth; local state adopts it. Only call
    /// this when `tracks_positions()` is true — `Broker::Sim` has no
    /// independent ledger at all (see `tracks_positions`), so this always
    /// returns an empty map that must never be mistaken for "flat".
    pub async fn positions(&self) -> Result<BTreeMap<String, f64>, String> {
        match self {
            Broker::Sim { .. } => Ok(BTreeMap::new()),
            Broker::Alpaca(b) => b.positions().await,
        }
    }

    /// Whether this broker maintains its own independent position ledger
    /// that startup reconciliation should treat as authoritative.
    ///
    /// `Broker::Sim` fills orders locally with no persistent account state
    /// of its own (see `submit` — it's a stateless per-order price
    /// calculation) — it never had a ledger to diverge from in the first
    /// place. Treating its always-empty `positions()` as authoritative was
    /// a bug: on every Sim-broker restart, reconcile() would silently wipe
    /// real accumulated local `Journal` state to nothing. For Sim, the
    /// local Journal already IS the single source of truth; reconciliation
    /// against Sim is a no-op by construction. `Broker::Alpaca` genuinely
    /// can diverge (manual intervention, missed fills across a crash) and
    /// remains authoritative as before.
    pub fn tracks_positions(&self) -> bool {
        match self {
            Broker::Sim { .. } => false,
            Broker::Alpaca(_) => true,
        }
    }

    /// Cancel orphaned open orders found during reconciliation.
    pub async fn cancel_open_orders(&self) -> Result<u32, String> {
        match self {
            Broker::Sim { .. } => Ok(0),
            Broker::Alpaca(b) => b.cancel_open_orders().await,
        }
    }
}

pub struct AlpacaBroker {
    base_url: String,
    key: String,
    secret: String,
    http: reqwest::Client,
}

impl AlpacaBroker {
    /// `live_endpoint` may only be true when the triple gate passed (startup.rs).
    pub fn new(live_endpoint: bool) -> Result<Self, String> {
        let key = std::env::var("ALPACA_API_KEY").map_err(|_| "ALPACA_API_KEY not set")?;
        let secret = std::env::var("ALPACA_SECRET_KEY").map_err(|_| "ALPACA_SECRET_KEY not set")?;
        Ok(Self {
            base_url: if live_endpoint {
                ALPACA_LIVE
            } else {
                ALPACA_PAPER
            }
            .to_string(),
            key,
            secret,
            http: reqwest::Client::new(),
        })
    }

    fn auth(&self, req: reqwest::RequestBuilder) -> reqwest::RequestBuilder {
        req.header("APCA-API-KEY-ID", &self.key)
            .header("APCA-API-SECRET-KEY", &self.secret)
    }

    async fn submit(&self, order: &Order) -> Result<Fill, String> {
        // Market order with idempotent client_order_id: Alpaca rejects a
        // duplicate id, so a crash mid-submit can never double-order.
        let body = serde_json::json!({
            "symbol": order.symbol,
            "qty": format!("{:.4}", order.qty.abs()),
            "side": if order.side == Side::Buy { "buy" } else { "sell" },
            "type": "market",
            "time_in_force": "day",
            "client_order_id": order.client_order_id,
        });
        let resp = self
            .auth(self.http.post(format!("{}/v2/orders", self.base_url)))
            .json(&body)
            .send()
            .await
            .map_err(|e| format!("submit: {e}"))?;
        if !resp.status().is_success() {
            return Err(format!(
                "submit {}: {}",
                resp.status(),
                resp.text().await.unwrap_or_default()
            ));
        }
        let v: serde_json::Value = resp.json().await.map_err(|e| e.to_string())?;
        let price = v["filled_avg_price"]
            .as_str()
            .and_then(|s| s.parse().ok())
            .unwrap_or(0.0);
        Ok(Fill {
            client_order_id: order.client_order_id.clone(),
            symbol: order.symbol.clone(),
            side: order.side,
            qty: order.qty,
            price,
            fees: 0.0,
            date: order.date.clone(),
        })
    }

    async fn positions(&self) -> Result<BTreeMap<String, f64>, String> {
        let resp = self
            .auth(self.http.get(format!("{}/v2/positions", self.base_url)))
            .send()
            .await
            .map_err(|e| format!("positions: {e}"))?;
        let items: Vec<serde_json::Value> = resp.json().await.map_err(|e| e.to_string())?;
        Ok(items
            .iter()
            .filter_map(|p| {
                Some((
                    p["symbol"].as_str()?.to_string(),
                    p["qty"].as_str()?.parse().ok()?,
                ))
            })
            .collect())
    }

    async fn cancel_open_orders(&self) -> Result<u32, String> {
        let resp = self
            .auth(self.http.delete(format!("{}/v2/orders", self.base_url)))
            .send()
            .await
            .map_err(|e| format!("cancel: {e}"))?;
        let items: Vec<serde_json::Value> = resp.json().await.unwrap_or_default();
        Ok(items.len() as u32)
    }
}
