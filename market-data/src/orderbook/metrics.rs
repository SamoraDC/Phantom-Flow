//! Order book metrics calculation

use rust_decimal::Decimal;
use serde::{Deserialize, Serialize};

/// Computed metrics for an order book
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct OrderBookMetrics {
    /// Mid price (average of best bid and ask)
    pub mid_price: Option<Decimal>,

    /// Spread in basis points
    pub spread_bps: Option<Decimal>,

    /// Simple imbalance: (bid_vol - ask_vol) / (bid_vol + ask_vol)
    pub imbalance: Option<Decimal>,

    /// Weighted imbalance (exponential decay with distance from mid)
    pub weighted_imbalance: Option<Decimal>,

    /// Total bid depth (volume)
    pub bid_depth: Decimal,

    /// Total ask depth (volume)
    pub ask_depth: Decimal,

    /// Number of bid levels
    pub bid_levels: usize,

    /// Number of ask levels
    pub ask_levels: usize,
}

impl OrderBookMetrics {
    /// Check if the order book is healthy (has valid data)
    pub fn is_healthy(&self) -> bool {
        self.mid_price.is_some()
            && self.spread_bps.is_some()
            && self.bid_levels > 0
            && self.ask_levels > 0
    }

    /// Get volume ratio (bid_depth / ask_depth)
    pub fn volume_ratio(&self) -> Option<Decimal> {
        if self.ask_depth > Decimal::ZERO {
            Some(self.bid_depth / self.ask_depth)
        } else {
            None
        }
    }
}
