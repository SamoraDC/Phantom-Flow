//! Error types for the market data handler

use thiserror::Error;

/// Market data handler errors
#[derive(Error, Debug)]
pub enum MarketDataError {
    #[error("WebSocket connection error: {0}")]
    WebSocketConnection(String),

    #[error("WebSocket message error: {0}")]
    WebSocketMessage(String),

    #[error("Failed to parse message: {0}")]
    ParseError(String),

    #[error("Order book error: {0}")]
    OrderBookError(String),

    #[error("REST API error: {0}")]
    RestApiError(String),

    #[error("IPC error: {0}")]
    IpcError(String),

    #[error("Configuration error: {0}")]
    ConfigError(String),

    #[error("Serialization error: {0}")]
    SerializationError(String),

    #[error("Sequence number mismatch: expected {expected}, got {got}")]
    SequenceMismatch { expected: u64, got: u64 },

    #[error("Connection timeout")]
    ConnectionTimeout,

    #[error("Max reconnection attempts exceeded")]
    MaxReconnectAttemptsExceeded,
}

impl From<tokio_tungstenite::tungstenite::Error> for MarketDataError {
    fn from(err: tokio_tungstenite::tungstenite::Error) -> Self {
        MarketDataError::WebSocketConnection(err.to_string())
    }
}

impl From<serde_json::Error> for MarketDataError {
    fn from(err: serde_json::Error) -> Self {
        MarketDataError::ParseError(err.to_string())
    }
}

impl From<reqwest::Error> for MarketDataError {
    fn from(err: reqwest::Error) -> Self {
        MarketDataError::RestApiError(err.to_string())
    }
}

impl From<std::io::Error> for MarketDataError {
    fn from(err: std::io::Error) -> Self {
        MarketDataError::IpcError(err.to_string())
    }
}

pub type Result<T> = std::result::Result<T, MarketDataError>;
