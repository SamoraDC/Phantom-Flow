#!/bin/bash
# Development environment setup script for QuantumFlow HFT
set -e

echo "=========================================="
echo "QuantumFlow HFT - Development Setup"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

check_command() {
    if command -v "$1" &> /dev/null; then
        echo -e "${GREEN}✓${NC} $1 is installed"
        return 0
    else
        echo -e "${RED}✗${NC} $1 is not installed"
        return 1
    fi
}

# Check prerequisites
echo "Checking prerequisites..."
echo ""

check_command "git" || { echo "Please install git"; exit 1; }
check_command "docker" || echo -e "${YELLOW}Warning: Docker not found (optional for local dev)${NC}"
check_command "make" || echo -e "${YELLOW}Warning: Make not found${NC}"

# Rust
echo ""
echo "Setting up Rust environment..."
if ! check_command "cargo"; then
    echo "Installing Rust..."
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    source "$HOME/.cargo/env"
fi
rustup update stable
rustup component add clippy rustfmt

# OCaml
echo ""
echo "Setting up OCaml environment..."
if ! check_command "opam"; then
    echo "Installing opam..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        brew install opam
    else
        sudo apt-get update && sudo apt-get install -y opam
    fi
fi
opam init -y --disable-sandboxing || true
eval $(opam env)
opam switch create 5.1.0 || opam switch 5.1.0
eval $(opam env)

echo "Installing OCaml dependencies..."
cd core
opam install . --deps-only -y
cd ..

# Python
echo ""
echo "Setting up Python environment..."
if ! check_command "python3"; then
    echo -e "${RED}Python 3 is required but not found${NC}"
    exit 1
fi

# Check Python version
PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "Python version: $PYTHON_VERSION"

# Create virtual environment
echo "Creating Python virtual environment..."
cd strategy
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"
cd ..

# Initialize data directory
echo ""
echo "Initializing data directory..."
mkdir -p data

# Create .env file if not exists
if [ ! -f .env ]; then
    echo "Creating .env file..."
    cat > .env << EOF
# QuantumFlow HFT Configuration

# Symbols to trade
SYMBOLS=BTCUSDT,ETHUSDT

# Database
DATABASE_URL=sqlite:///data/trades.db

# Risk parameters
RISK_MAX_POSITION=1.0
RISK_MAX_DRAWDOWN=0.05

# Timezone for Shabbat calculation
TIMEZONE=America/Sao_Paulo
SHABBAT_LATITUDE=-23.5505
SHABBAT_LONGITUDE=-46.6333

# Optional: Telegram notifications
# TELEGRAM_BOT_TOKEN=your_bot_token
# TELEGRAM_CHAT_ID=your_chat_id

# Logging
LOG_LEVEL=INFO
RUST_LOG=info
EOF
    echo -e "${GREEN}✓${NC} Created .env file - please configure as needed"
fi

# Build projects
echo ""
echo "Building projects..."

echo "Building Rust market-data..."
cd market-data
cargo build
cd ..

echo "Building OCaml core..."
cd core
eval $(opam env)
dune build
cd ..

# Done
echo ""
echo "=========================================="
echo -e "${GREEN}Setup complete!${NC}"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Configure .env file with your settings"
echo "  2. Run 'make dev' to start the development environment"
echo "  3. Or run components individually:"
echo "     - Rust: cd market-data && cargo run"
echo "     - OCaml: cd core && dune exec risk_gateway"
echo "     - Python: cd strategy && uvicorn src.api.main:app --reload"
echo ""
