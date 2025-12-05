# QuantumFlow HFT Architecture

This document describes the system architecture of QuantumFlow, a high-frequency paper trading system designed for portfolio demonstration.

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           QuantumFlow HFT System                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                   │
│  │  Binance     │    │   Market     │    │    Core      │                   │
│  │  WebSocket   │───▶│    Data      │───▶│    Risk      │                   │
│  │  Streams     │    │   (Rust)     │    │   (OCaml)    │                   │
│  └──────────────┘    └──────────────┘    └──────────────┘                   │
│                              │                   │                           │
│                              │                   │                           │
│                              ▼                   ▼                           │
│                      ┌──────────────────────────────────┐                   │
│                      │       Strategy Engine             │                   │
│                      │          (Python)                 │                   │
│                      │                                   │                   │
│                      │  ┌─────────┐  ┌─────────────┐    │                   │
│                      │  │Features │  │  Imbalance  │    │                   │
│                      │  │  Calc   │  │  Strategy   │    │                   │
│                      │  └─────────┘  └─────────────┘    │                   │
│                      │                                   │                   │
│                      │  ┌─────────┐  ┌─────────────┐    │                   │
│                      │  │ Paper   │  │   REST      │    │                   │
│                      │  │ Broker  │  │    API      │    │                   │
│                      │  └─────────┘  └─────────────┘    │                   │
│                      └──────────────────────────────────┘                   │
│                                      │                                       │
│                                      ▼                                       │
│                              ┌──────────────┐                                │
│                              │   SQLite     │                                │
│                              │   Database   │                                │
│                              └──────────────┘                                │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Components

### 1. Market Data Handler (Rust)

**Purpose**: High-performance WebSocket connection management and order book reconstruction.

**Technology Choice**: Rust was chosen for its:
- Zero-cost abstractions for low-latency processing
- Memory safety without garbage collection
- Excellent async ecosystem (tokio)
- Predictable performance characteristics

**Key Features**:
- Maintains persistent WebSocket connections to Binance
- Automatic reconnection with exponential backoff
- Order book reconstruction from snapshots and incremental updates
- Calculates microstructure metrics (spread, imbalance)
- Publishes normalized data via Unix domain socket

**Performance Targets**:
- Message processing: < 100μs
- Memory usage: < 50MB
- Zero allocations in hot path

### 2. Core Risk Engine (OCaml)

**Purpose**: Type-safe position management and risk validation.

**Technology Choice**: OCaml was chosen for its:
- Algebraic data types preventing invalid states
- Exhaustive pattern matching
- Immutable-by-default data structures
- Strong static typing catching errors at compile time

**Key Features**:
- Position limit enforcement
- Drawdown circuit breakers
- Rate limiting
- Pre-trade risk validation
- Real-time P&L calculation

**Type Safety Example**:
```ocaml
type order_status =
  | Pending
  | PartiallyFilled of Decimal.t
  | Filled
  | Cancelled
  | Rejected of string
```
Invalid states like "filled with negative quantity" are unrepresentable.

### 3. Strategy Engine (Python)

**Purpose**: Trading strategy implementation and system orchestration.

**Technology Choice**: Python was chosen for its:
- Rapid prototyping for strategy development
- Rich ecosystem (numpy, pandas, scikit-learn)
- FastAPI for clean REST APIs
- Easy debugging and modification

**Key Features**:
- Order flow imbalance strategy
- Feature engineering (volatility, momentum)
- Paper broker with realistic simulation
- Shabbat pause scheduler
- REST API for monitoring

### 4. Report Generator

**Purpose**: Generate performance visualizations for the README.

**Features**:
- Equity curve plotting
- Drawdown visualization
- P&L distribution histogram
- Hourly performance heatmap
- Automatic README updates via GitHub Actions

## Data Flow

1. **Market Data Ingestion**:
   - Binance WebSocket → Rust parser → Order book update
   - Metrics calculated: mid price, spread, imbalance

2. **Signal Generation**:
   - Python receives order book state
   - Features calculated: volatility, momentum
   - Strategy evaluates conditions
   - Signal generated with confidence score

3. **Risk Check**:
   - Signal sent to OCaml risk engine
   - Position limits checked
   - Drawdown validated
   - Approved/rejected/adjusted response

4. **Order Execution**:
   - Paper broker simulates fill
   - Slippage and fees applied
   - Position updated
   - Trade persisted to SQLite

5. **Reporting**:
   - Daily GitHub Action triggers
   - Reads trades from database
   - Generates charts
   - Updates README automatically

## Communication Protocols

### Rust ↔ OCaml
- Unix domain socket
- MessagePack binary serialization
- Length-prefixed messages

### Python ↔ OCaml
- HTTP REST API
- JSON payloads
- Health checks via /health endpoint

### Python ↔ SQLite
- aiosqlite for async operations
- Connection pooling
- WAL mode for concurrent reads

## Deployment Architecture

```
                    ┌─────────────────┐
                    │   GitHub        │
                    │   Actions       │
                    │                 │
                    │ ┌─────────────┐ │
                    │ │ CI Tests    │ │
                    │ └─────────────┘ │
                    │ ┌─────────────┐ │
                    │ │ Deploy      │ │
                    │ └─────────────┘ │
                    │ ┌─────────────┐ │
                    │ │ Reports     │ │
                    │ └─────────────┘ │
                    │ ┌─────────────┐ │
                    │ │ Health      │ │
                    │ └─────────────┘ │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │    Fly.io       │
                    │    (GRU)        │
                    │                 │
                    │ ┌─────────────┐ │
                    │ │ Supervisor  │ │
                    │ │             │ │
                    │ │ ┌─────────┐ │ │
                    │ │ │ Rust    │ │ │
                    │ │ └─────────┘ │ │
                    │ │ ┌─────────┐ │ │
                    │ │ │ OCaml   │ │ │
                    │ │ └─────────┘ │ │
                    │ │ ┌─────────┐ │ │
                    │ │ │ Python  │ │ │
                    │ │ └─────────┘ │ │
                    │ └─────────────┘ │
                    │                 │
                    │ ┌─────────────┐ │
                    │ │ Volume      │ │
                    │ │ (SQLite)    │ │
                    │ └─────────────┘ │
                    └─────────────────┘
```

## Monitoring & Alerting

- **Health Checks**: Every 15 minutes via GitHub Actions
- **Telegram Notifications**: Trade executions, daily reports, errors
- **Automatic Recovery**: Fly.io restarts on health check failure

## Security Considerations

- No API keys for trading (paper trading only)
- Database in persistent volume
- Secrets via Fly.io encrypted storage
- No sensitive data in logs
