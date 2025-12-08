#!/bin/bash
# Run all components locally for development
set -e

echo "Starting QuantumFlow HFT locally..."

# Load environment
source .env 2>/dev/null || true

# Create data directory
mkdir -p data

# Start components in background
echo "Starting Risk Gateway (OCaml)..."
cd core
eval $(opam env 2>/dev/null) || true
dune exec risk_gateway &
RISK_PID=$!
cd ..

sleep 2

echo "Starting Strategy Engine (Python)..."
cd strategy
source .venv/bin/activate 2>/dev/null || true
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 &
STRATEGY_PID=$!
cd ..

sleep 2

echo "Starting Market Data Handler (Rust)..."
cd market-data
cargo run --release &
MARKET_PID=$!
cd ..

echo ""
echo "All components started!"
echo "  Risk Gateway PID: $RISK_PID"
echo "  Strategy Engine PID: $STRATEGY_PID"
echo "  Market Data PID: $MARKET_PID"
echo ""
echo "API available at: http://localhost:8000"
echo "Health check: http://localhost:8000/health"
echo ""
echo "Press Ctrl+C to stop all components"

# Trap Ctrl+C and cleanup
cleanup() {
    echo ""
    echo "Stopping components..."
    kill $RISK_PID 2>/dev/null || true
    kill $STRATEGY_PID 2>/dev/null || true
    kill $MARKET_PID 2>/dev/null || true
    echo "Done."
    exit 0
}

trap cleanup SIGINT SIGTERM

# Wait for all processes
wait
