//! Order book manager
//!
//! Manages multiple order books for different symbols.

use std::collections::HashMap;

use super::{OrderBook, OrderBookState};
use crate::parser::{DepthUpdate, OrderBookSnapshot};

/// Manages order books for multiple symbols
#[derive(Debug, Default)]
pub struct OrderBookManager {
    books: HashMap<String, OrderBook>,
    max_depth: usize,
}

impl OrderBookManager {
    /// Create a new order book manager
    pub fn new() -> Self {
        Self {
            books: HashMap::new(),
            max_depth: 20,
        }
    }

    /// Create with custom depth
    pub fn with_depth(max_depth: usize) -> Self {
        Self {
            books: HashMap::new(),
            max_depth,
        }
    }

    /// Initialize an order book with a snapshot
    pub fn init_book(&mut self, symbol: &str, snapshot: OrderBookSnapshot) {
        let mut book = OrderBook::new(symbol, self.max_depth);
        book.init_snapshot(&snapshot);
        self.books.insert(symbol.to_string(), book);
    }

    /// Apply a depth update to the appropriate book
    pub fn apply_update(&mut self, update: &DepthUpdate) -> bool {
        if let Some(book) = self.books.get_mut(&update.symbol) {
            book.apply_update(update)
        } else {
            false
        }
    }

    /// Get the state of a specific book
    pub fn get_state(&self, symbol: &str) -> Option<OrderBookState> {
        self.books.get(symbol).map(|book| book.state())
    }

    /// Get states of all books
    pub fn get_all_states(&self) -> Vec<OrderBookState> {
        self.books.values().map(|book| book.state()).collect()
    }

    /// Check if a book is initialized
    pub fn is_initialized(&self, symbol: &str) -> bool {
        self.books
            .get(symbol)
            .map(|book| book.is_initialized())
            .unwrap_or(false)
    }

    /// Get the last update ID for a symbol
    pub fn last_update_id(&self, symbol: &str) -> Option<u64> {
        self.books.get(symbol).map(|book| book.last_update_id())
    }

    /// Get list of symbols being tracked
    pub fn symbols(&self) -> Vec<String> {
        self.books.keys().cloned().collect()
    }

    /// Check if a symbol exists
    pub fn has_symbol(&self, symbol: &str) -> bool {
        self.books.contains_key(symbol)
    }
}
