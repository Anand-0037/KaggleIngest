# Build stage
FROM python:3.13-slim-bookworm AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Set working directory
WORKDIR /app

# Copy dependency definition and lockfile
COPY pyproject.toml uv.lock ./

# Install dependencies into a virtual environment
RUN uv venv /opt/venv && \
  uv sync --frozen --no-dev

# Runtime stage
FROM python:3.13-slim-bookworm

# Install curl for health checks
RUN apt-get update && apt-get install -y --no-install-recommends curl && \
  rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy virtual environment
COPY --from=builder /opt/venv /opt/venv

# Make sure we use the virtualenv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY . .

# Create non-root user for security
RUN useradd -m appuser && \
  mkdir -p /app/outputs && \
  chown -R appuser:appuser /app

USER appuser

# Expose port (FastAPI default or configurable)
EXPOSE 8000

# Health check (use PORT env var if set)
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

# Entrypoint - use shell form to expand $PORT at runtime
CMD uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}

