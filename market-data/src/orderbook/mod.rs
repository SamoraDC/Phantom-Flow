//! Order book module
//!
//! Maintains synchronized order book state from Binance depth updates.

mod book;
mod manager;
mod metrics;

pub use book::OrderBook;
pub use manager::OrderBookManager;
pub use metrics::OrderBookMetrics;

use rust_decimal::Decimal;
use serde::{Deserialize, Serialize};

/// Side of the order book
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum Side {
    Bid,
    Ask,
}

/// A single level in the order book
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Level {
    pub price: Decimal,
    pub quantity: Decimal,
}

/// Order book state to be published
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OrderBookState {
    pub symbol: String,
    pub timestamp: u64,
    pub last_update_id: u64,
    pub bids: Vec<Level>,
    pub asks: Vec<Level>,
    pub metrics: OrderBookMetrics,
}
