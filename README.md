# QuantumFlow HFT Paper Trading

[![CI](https://github.com/SamoraDC/quantumflow-hft/actions/workflows/ci.yml/badge.svg)](https://github.com/SamoraDC/quantumflow-hft/actions/workflows/ci.yml)
[![Deploy](https://github.com/SamoraDC/quantumflow-hft/actions/workflows/deploy.yml/badge.svg)](https://github.com/SamoraDC/quantumflow-hft/actions/workflows/deploy.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A high-frequency paper trading system demonstrating multi-language systems engineering with Rust, OCaml, and Python. Designed as a portfolio project showcasing low-latency market data processing, type-safe risk management, and quantitative trading strategies.

## Features

- **Real-time Market Data** (Rust): WebSocket connection to Binance with order book reconstruction
- **Type-Safe Risk Engine** (OCaml): Position limits, drawdown circuit breakers, P&L calculation
- **Trading Strategy** (Python): Order flow imbalance strategy with volatility adjustment
- **Paper Trading**: Realistic execution simulation with slippage and fees
- **Shabbat Pause**: Automatic trading pause from Friday to Saturday sunset
- **Live Dashboard**: Auto-updating README with performance charts via GitHub Actions
- **Free Deployment**: Runs 24/6 on Fly.io free tier

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Binance   │────▶│    Rust     │────▶│   OCaml     │
│  WebSocket  │     │ Market Data │     │ Risk Engine │
└─────────────┘     └─────────────┘     └─────────────┘
                           │                   │
                           └───────┬───────────┘
                                   ▼
                          ┌─────────────────┐
                          │     Python      │
                          │ Strategy Engine │
                          │   + REST API    │
                          └────────┬────────┘
                                   │
                          ┌────────▼────────┐
                          │     SQLite      │
                          │    Database     │
                          └─────────────────┘
```

### Why This Tech Stack?

| Component | Language | Reason |
|-----------|----------|--------|
| Market Data | **Rust** | Zero-cost abstractions, memory safety, excellent async runtime |
| Risk Engine | **OCaml** | Algebraic data types prevent invalid states, exhaustive pattern matching |
| Strategy | **Python** | Rapid prototyping, rich data science ecosystem, easy modification |

## Quick Start

### Prerequisites

- Rust 1.75+
- OCaml 5.1+ with opam
- Python 3.11+
- Docker (optional)

### Setup

```bash
# Clone the repository
git clone https://github.com/SamoraDC/quantumflow-hft.git
cd quantumflow-hft

# Run setup script (installs all dependencies)
./scripts/setup-dev.sh

# Start all components locally
./scripts/run-local.sh
```

### Using Docker

```bash
docker-compose up --build
```

## Project Structure

```
quantumflow-hft/
├── market-data/          # Rust - WebSocket & order book
│   └── src/
│       ├── websocket/    # Connection management
│       ├── parser/       # Message deserialization
│       ├── orderbook/    # Order book data structure
│       └── publisher/    # IPC to other components
│
├── core/                 # OCaml - Risk engine
│   └── lib/
│       ├── types/        # Domain types (Order, Trade, Position)
│       ├── orderbook/    # Type-safe order book
│       ├── risk/         # Risk validation & limits
│       └── pnl/          # P&L calculation
│
├── strategy/             # Python - Trading strategy
│   └── src/
│       ├── signals/      # Trading strategies
│       ├── features/     # Microstructure features
│       ├── broker/       # Paper broker
│       ├── api/          # REST API (FastAPI)
│       └── storage/      # SQLite persistence
│
├── reports/              # Report generator
│   ├── generate.py       # Chart generation
│   └── templates/        # README templates
│
├── docs/                 # Documentation
│   ├── architecture.md   # System design
│   ├── strategies.md     # Trading logic
│   └── deployment.md     # Deploy guide
│
└── .github/workflows/    # CI/CD
    ├── ci.yml            # Tests on every push
    ├── deploy.yml        # Deploy to Fly.io
    ├── daily-report.yml  # Update charts daily
    └── health-check.yml  # Monitor every 15min
```

## Trading Strategy

The primary strategy exploits **order book imbalance** - when bid volume significantly exceeds ask volume, buying pressure tends to push prices up.

### Signal Generation

1. Calculate imbalance: `(bid_vol - ask_vol) / (bid_vol + ask_vol)`
2. Apply weighted decay (closer levels matter more)
3. Require persistence (3+ ticks in same direction)
4. Confirm with price momentum
5. Filter by spread and volatility

### Risk Management

- **Position Limits**: Max 1 BTC per symbol
- **Drawdown Circuit Breaker**: Pauses at 5% drawdown
- **Rate Limiting**: Max 60 orders/minute
- **Stop Loss**: 2x ATR below entry

<!-- METRICS_START -->
## Live Performance

*System starting - metrics will appear after first trades*

| Metric | Value |
|--------|-------|
| Total Trades | 0 |
| Win Rate | 0% |
| Total P&L | $0.00 |
| Sharpe Ratio | - |
| Max Drawdown | 0% |

*Charts will be generated daily by GitHub Actions*
<!-- METRICS_END -->

## Deployment

### Deploy to Fly.io

```bash
# Install flyctl
curl -L https://fly.io/install.sh | sh

# Login and deploy
flyctl auth login
flyctl launch
flyctl deploy
```

### GitHub Actions Setup

Add these secrets to your repository:

| Secret | Description |
|--------|-------------|
| `FLY_API_TOKEN` | Fly.io deployment token |
| `TELEGRAM_BOT_TOKEN` | Optional: For notifications |
| `TELEGRAM_CHAT_ID` | Optional: Telegram chat ID |

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/status` | GET | System status |
| `/account` | GET | Account state |
| `/positions` | GET | Open positions |
| `/trades` | GET | Trade history |
| `/metrics` | GET | Performance metrics |

## Development

### Running Tests

```bash
# All tests
make test

# Individual components
cd market-data && cargo test
cd core && dune test
cd strategy && pytest
```

### Linting

```bash
make lint
```

### Benchmarks

```bash
cd market-data && cargo bench
```

## Documentation

- [Architecture](docs/architecture.md) - System design and data flow
- [Strategies](docs/strategies.md) - Trading strategy documentation
- [Deployment](docs/deployment.md) - Deploy and configuration guide

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a pull request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

This is a **paper trading** system for educational and portfolio demonstration purposes only. It does not execute real trades or handle real money. Past simulated performance does not guarantee future results.

---

Built with Rust, OCaml, and Python
