# QuantumFlow HFT Paper Trading - Multi-stage Dockerfile
# Combines Rust, OCaml, and Python components into a single optimized image

# ============================================================================
# Stage 1: Rust Builder
# ============================================================================
FROM rust:1.75-slim-bookworm AS rust-builder

RUN apt-get update && apt-get install -y \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/market-data

# Copy manifests first for caching
COPY market-data/Cargo.toml market-data/Cargo.lock ./

# Create dummy main.rs for dependency caching
RUN mkdir src && echo "fn main() {}" > src/main.rs
RUN cargo build --release && rm -rf src

# Copy actual source code
COPY market-data/src ./src

# Build release binary
RUN touch src/main.rs && cargo build --release

# ============================================================================
# Stage 2: OCaml Builder
# ============================================================================
FROM ocaml/opam:debian-12-ocaml-5.1 AS ocaml-builder

USER opam
WORKDIR /home/opam/app

# Install dependencies
RUN opam update && opam install -y \
    dune \
    core \
    core_unix \
    yojson \
    ppx_deriving \
    ppx_deriving_yojson \
    lwt \
    lwt_ppx \
    cohttp-lwt-unix \
    alcotest

# Copy project files
COPY --chown=opam:opam core/ .

# Build
RUN eval $(opam env) && dune build --release

# ============================================================================
# Stage 3: Python Builder
# ============================================================================
FROM python:3.11-slim-bookworm AS python-builder

WORKDIR /app/strategy

# Install build dependencies
RUN pip install --no-cache-dir poetry

# Copy dependency files
COPY strategy/pyproject.toml strategy/poetry.lock* ./

# Install dependencies
RUN poetry config virtualenvs.create false \
    && poetry install --no-dev --no-interaction --no-ansi

# Copy source code
COPY strategy/src ./src

# ============================================================================
# Stage 4: Final Runtime Image
# ============================================================================
FROM python:3.11-slim-bookworm AS runtime

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    libssl3 \
    ca-certificates \
    curl \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy Rust binary
COPY --from=rust-builder /app/market-data/target/release/market-data /app/bin/market-data

# Copy OCaml binary
COPY --from=ocaml-builder /home/opam/app/_build/default/bin/risk_gateway.exe /app/bin/risk_gateway

# Copy Python application
COPY --from=python-builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY strategy/src /app/strategy/src

# Copy supervisor configuration
COPY deploy/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Copy entrypoint script
COPY deploy/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Create data directory
RUN mkdir -p /data

# Expose ports
EXPOSE 8000 9090

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start all services via supervisor
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
