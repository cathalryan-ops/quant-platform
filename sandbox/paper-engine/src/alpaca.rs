//! Alpaca market-data websocket feed (IEX). DATA stream only — this crate
//! has no trading-API client by construction.
//!
//! Requires ALPACA_API_KEY / ALPACA_SECRET_KEY (data/paper keys; live keys
//! never exist in agent environments). Daily bars accumulate intraday; a
//! session is emitted when the stream's bar date rolls over, so in a live
//! run the engine acts once per completed session, matching the sim feed's
//! semantics.

use std::collections::BTreeMap;

use engine_core::engine::Bar;
use futures_util::{SinkExt, StreamExt};
use serde_json::json;
use tokio_tungstenite::tungstenite::Message;

const IEX_STREAM: &str = "wss://stream.data.alpaca.markets/v2/iex";

pub struct AlpacaFeed {
    universe: Vec<String>,
    ws: tokio_tungstenite::WebSocketStream<
        tokio_tungstenite::MaybeTlsStream<tokio::net::TcpStream>,
    >,
    pending: BTreeMap<String, Bar>,
    pending_date: Option<String>,
}

impl AlpacaFeed {
    pub async fn connect(universe: Vec<String>) -> Result<Self, String> {
        let key = std::env::var("ALPACA_API_KEY").map_err(|_| "ALPACA_API_KEY not set")?;
        let secret = std::env::var("ALPACA_SECRET_KEY").map_err(|_| "ALPACA_SECRET_KEY not set")?;
        let (mut ws, _) = tokio_tungstenite::connect_async(IEX_STREAM)
            .await
            .map_err(|e| format!("connect {IEX_STREAM}: {e}"))?;
        let auth = json!({"action": "auth", "key": key, "secret": secret});
        ws.send(Message::text(auth.to_string()))
            .await
            .map_err(|e| format!("auth send: {e}"))?;
        let sub = json!({"action": "subscribe", "dailyBars": universe});
        ws.send(Message::text(sub.to_string()))
            .await
            .map_err(|e| format!("subscribe send: {e}"))?;
        tracing::info!(?universe, "alpaca feed connected (IEX daily bars)");
        Ok(Self {
            universe,
            ws,
            pending: BTreeMap::new(),
            pending_date: None,
        })
    }

    pub async fn next_session(&mut self) -> Result<Option<Vec<Bar>>, String> {
        while let Some(msg) = self.ws.next().await {
            let msg = msg.map_err(|e| format!("ws: {e}"))?;
            let Message::Text(text) = msg else { continue };
            let Ok(items) = serde_json::from_str::<Vec<serde_json::Value>>(&text) else {
                continue;
            };
            for item in items {
                if item["T"] != "d" {
                    continue;
                }
                let date = item["t"]
                    .as_str()
                    .unwrap_or("")
                    .get(..10)
                    .unwrap_or("")
                    .to_string();
                let bar = Bar {
                    symbol: item["S"].as_str().unwrap_or("").to_string(),
                    date: date.clone(),
                    open: item["o"].as_f64().unwrap_or(0.0),
                    high: item["h"].as_f64().unwrap_or(0.0),
                    low: item["l"].as_f64().unwrap_or(0.0),
                    close: item["c"].as_f64().unwrap_or(0.0),
                    volume: item["v"].as_f64().unwrap_or(0.0),
                };
                // Date rollover => the previous session is complete.
                if let Some(prev) = &self.pending_date {
                    if *prev != date && self.pending.len() == self.universe.len() {
                        let done: Vec<Bar> =
                            std::mem::take(&mut self.pending).into_values().collect();
                        self.pending.insert(bar.symbol.clone(), bar);
                        self.pending_date = Some(date);
                        return Ok(Some(done));
                    }
                }
                self.pending_date = Some(date);
                self.pending.insert(bar.symbol.clone(), bar);
            }
        }
        // Stream closed: flush whatever complete session is pending.
        if self.pending.len() == self.universe.len() {
            return Ok(Some(
                std::mem::take(&mut self.pending).into_values().collect(),
            ));
        }
        Ok(None)
    }
}
