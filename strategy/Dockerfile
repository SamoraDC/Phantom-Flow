# Python Strategy Engine - Dockerfile
FROM python:3.11-slim-bookworm AS builder

WORKDIR /app

# Install build dependencies
RUN pip install --no-cache-dir poetry

# Copy dependency files
COPY pyproject.toml poetry.lock* ./

# Install dependencies
RUN poetry config virtualenvs.create false \
    && poetry install --no-dev --no-interaction --no-ansi

# Runtime image
FROM python:3.11-slim-bookworm

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy source code
COPY src ./src

# Create data directory
RUN mkdir -p /data

ENV DATABASE_URL=sqlite:///data/trades.db
ENV CORE_API_URL=http://localhost:8081
ENV TIMEZONE=America/Sao_Paulo
ENV PYTHONPATH=/app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
