# Rust Market Data Handler - Dockerfile
FROM rust:1.75-slim-bookworm AS builder

RUN apt-get update && apt-get install -y \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy manifests for caching
COPY Cargo.toml Cargo.lock ./

# Create dummy source for dependency caching
RUN mkdir src && echo "fn main() {}" > src/main.rs
RUN cargo build --release && rm -rf src

# Copy actual source
COPY src ./src
COPY benches ./benches

# Build release
RUN touch src/main.rs && cargo build --release

# Runtime image
FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y \
    ca-certificates \
    libssl3 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/target/release/market-data /usr/local/bin/market-data

ENV RUST_LOG=info
ENV SYMBOLS=BTCUSDT,ETHUSDT
ENV WS_ENDPOINT=wss://stream.binance.com:9443/ws
ENV REST_ENDPOINT=https://api.binance.com/api/v3
ENV IPC_SOCKET_PATH=/tmp/quantumflow.sock

EXPOSE 9090

CMD ["market-data"]
