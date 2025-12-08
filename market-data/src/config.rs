//! Configuration module for the market data handler

use serde::Deserialize;
use std::env;

/// Application configuration
#[derive(Debug, Clone, Deserialize)]
pub struct Config {
    /// Trading symbols to subscribe to (e.g., ["BTCUSDT", "ETHUSDT"])
    pub symbols: Vec<String>,

    /// WebSocket endpoint for Binance
    pub ws_endpoint: String,

    /// REST API endpoint for snapshots
    pub rest_endpoint: String,

    /// IPC socket path for publishing data
    pub ipc_socket_path: String,

    /// Order book depth levels to maintain
    pub depth_levels: usize,

    /// Reconnection settings
    pub reconnect_delay_ms: u64,
    pub max_reconnect_attempts: u32,

    /// Health check interval in seconds
    pub health_check_interval_secs: u64,
}

impl Config {
    /// Load configuration from environment variables
    pub fn load() -> anyhow::Result<Self> {
        dotenvy::dotenv().ok();

        let symbols: Vec<String> = env::var("SYMBOLS")
            .unwrap_or_else(|_| "BTCUSDT,ETHUSDT".to_string())
            .split(',')
            .map(|s| s.trim().to_uppercase())
            .collect();

        Ok(Self {
            symbols,
            ws_endpoint: env::var("WS_ENDPOINT")
                .unwrap_or_else(|_| "wss://stream.binance.com:9443/ws".to_string()),
            rest_endpoint: env::var("REST_ENDPOINT")
                .unwrap_or_else(|_| "https://api.binance.com/api/v3".to_string()),
            ipc_socket_path: env::var("IPC_SOCKET_PATH")
                .unwrap_or_else(|_| "/tmp/quantumflow.sock".to_string()),
            depth_levels: env::var("DEPTH_LEVELS")
                .unwrap_or_else(|_| "20".to_string())
                .parse()
                .unwrap_or(20),
            reconnect_delay_ms: env::var("RECONNECT_DELAY_MS")
                .unwrap_or_else(|_| "1000".to_string())
                .parse()
                .unwrap_or(1000),
            max_reconnect_attempts: env::var("MAX_RECONNECT_ATTEMPTS")
                .unwrap_or_else(|_| "10".to_string())
                .parse()
                .unwrap_or(10),
            health_check_interval_secs: env::var("HEALTH_CHECK_INTERVAL_SECS")
                .unwrap_or_else(|_| "30".to_string())
                .parse()
                .unwrap_or(30),
        })
    }
}

impl Default for Config {
    fn default() -> Self {
        Self {
            symbols: vec!["BTCUSDT".to_string()],
            ws_endpoint: "wss://stream.binance.com:9443/ws".to_string(),
            rest_endpoint: "https://api.binance.com/api/v3".to_string(),
            ipc_socket_path: "/tmp/quantumflow.sock".to_string(),
            depth_levels: 20,
            reconnect_delay_ms: 1000,
            max_reconnect_attempts: 10,
            health_check_interval_secs: 30,
        }
    }
}
