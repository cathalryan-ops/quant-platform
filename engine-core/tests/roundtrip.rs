//! Every contracts/examples/*.json must round-trip losslessly through the
//! typed mirrors: parse -> serialize -> semantically identical JSON.

use engine_core::contracts::{BacktestResult, Event, PaperResult, Promotion, StrategyManifest};
use serde_json::Value;
use std::fs;
use std::path::PathBuf;

fn roundtrip<T>(file: &str)
where
    T: serde::de::DeserializeOwned + serde::Serialize,
{
    let path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../contracts/examples")
        .join(file);
    let raw = fs::read_to_string(&path).unwrap_or_else(|e| panic!("read {path:?}: {e}"));
    let original: Value = serde_json::from_str(&raw).unwrap();
    let typed: T = serde_json::from_str(&raw).unwrap_or_else(|e| panic!("parse {file}: {e}"));
    let back = serde_json::to_value(&typed).unwrap();
    assert_eq!(original, back, "{file} did not round-trip");
}

#[test]
fn strategy_manifest_roundtrips() {
    roundtrip::<StrategyManifest>("strategy_manifest.json");
}

#[test]
fn backtest_result_roundtrips() {
    roundtrip::<BacktestResult>("backtest_result.json");
}

#[test]
fn paper_result_roundtrips() {
    roundtrip::<PaperResult>("paper_result.json");
}

#[test]
fn promotion_roundtrips() {
    roundtrip::<Promotion>("promotion.json");
}

#[test]
fn event_roundtrips() {
    roundtrip::<Event>("events.json");
}
