# QuantumFlow HFT Paper Trading - Makefile
# Orchestrates build, test, and deployment for all components

.PHONY: all build test clean dev deploy rust-build ocaml-build python-install

# Default target
all: build

# ============================================================================
# Build targets
# ============================================================================

build: rust-build ocaml-build python-install
	@echo "All components built successfully"

rust-build:
	@echo "Building Rust market-data component..."
	cd market-data && cargo build --release

ocaml-build:
	@echo "Building OCaml core component..."
	cd core && dune build

python-install:
	@echo "Installing Python strategy component..."
	cd strategy && pip install -e .

# ============================================================================
# Test targets
# ============================================================================

test: rust-test ocaml-test python-test
	@echo "All tests passed"

rust-test:
	@echo "Running Rust tests..."
	cd market-data && cargo test

ocaml-test:
	@echo "Running OCaml tests..."
	cd core && dune test

python-test:
	@echo "Running Python tests..."
	cd strategy && pytest tests/ -v

# ============================================================================
# Lint targets
# ============================================================================

lint: rust-lint ocaml-lint python-lint
	@echo "All lints passed"

rust-lint:
	cd market-data && cargo clippy -- -D warnings

ocaml-lint:
	cd core && dune build @fmt

python-lint:
	cd strategy && ruff check src/ tests/
	cd strategy && mypy src/

# ============================================================================
# Development targets
# ============================================================================

dev:
	@echo "Starting development environment..."
	docker-compose up --build

dev-rust:
	cd market-data && cargo watch -x run

dev-python:
	cd strategy && uvicorn src.api.main:app --reload --port 8000

# ============================================================================
# Benchmark targets
# ============================================================================

bench:
	cd market-data && cargo bench

# ============================================================================
# Deployment targets
# ============================================================================

deploy:
	fly deploy

deploy-staging:
	fly deploy --config fly.staging.toml

# ============================================================================
# Utility targets
# ============================================================================

clean:
	cd market-data && cargo clean
	cd core && dune clean
	cd strategy && rm -rf .pytest_cache __pycache__ *.egg-info
	rm -rf data/*.db

setup-dev:
	./scripts/setup-dev.sh

download-history:
	python scripts/download-history.py

generate-report:
	python reports/generate.py

# ============================================================================
# Docker targets
# ============================================================================

docker-build:
	docker build -t quantumflow-hft .

docker-run:
	docker run -d --name quantumflow -v $(PWD)/data:/data quantumflow-hft

docker-stop:
	docker stop quantumflow && docker rm quantumflow

# ============================================================================
# Help
# ============================================================================

help:
	@echo "QuantumFlow HFT Paper Trading - Available targets:"
	@echo ""
	@echo "  build          - Build all components"
	@echo "  test           - Run all tests"
	@echo "  lint           - Run all linters"
	@echo "  dev            - Start development environment with docker-compose"
	@echo "  bench          - Run Rust benchmarks"
	@echo "  deploy         - Deploy to Fly.io"
	@echo "  clean          - Clean all build artifacts"
	@echo "  setup-dev      - Setup development environment"
	@echo "  generate-report - Generate performance report"
	@echo "  help           - Show this help message"
