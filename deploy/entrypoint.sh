#!/bin/bash
set -e

# QuantumFlow HFT Paper Trading - Entrypoint Script
# Initializes the environment and starts all services

echo "========================================"
echo "QuantumFlow HFT Paper Trading System"
echo "========================================"
echo ""

# Create necessary directories
mkdir -p /var/log/supervisor
mkdir -p /data

# Initialize database if it doesn't exist
if [ ! -f /data/trades.db ]; then
    echo "Initializing SQLite database..."
    python -c "
from strategy.src.storage.database import init_database
init_database('/data/trades.db')
print('Database initialized successfully')
"
fi

# Display configuration
echo "Configuration:"
echo "  Symbols: ${SYMBOLS:-BTCUSDT,ETHUSDT}"
echo "  Timezone: ${TIMEZONE:-America/Sao_Paulo}"
echo "  Max Position: ${RISK_MAX_POSITION:-1.0}"
echo "  Max Drawdown: ${RISK_MAX_DRAWDOWN:-0.05}"
echo ""

# Check Binance connectivity
echo "Checking Binance API connectivity..."
if curl -s --connect-timeout 5 https://api.binance.com/api/v3/ping > /dev/null; then
    echo "  Binance API: OK"
else
    echo "  Binance API: WARNING - Unable to connect"
fi
echo ""

echo "Starting services..."
echo ""

# Execute the main command (supervisord)
exec "$@"
