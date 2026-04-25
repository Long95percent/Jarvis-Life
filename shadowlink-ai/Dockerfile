# ============================================
# ShadowLink AI Service — Multi-stage Dockerfile
# ============================================

# ── Stage 1: Build ──
FROM python:3.10-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency definition first for layer caching
COPY pyproject.toml .
RUN pip install --no-cache-dir --prefix=/install .

# ── Stage 2: Runtime ──
FROM python:3.10-slim AS runtime

# Labels
LABEL maintainer="ShadowLink Team"
LABEL description="ShadowLink AI Service — Agent, RAG, MCP, Tools"
LABEL version="0.1.0"

WORKDIR /app

# Install minimal runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Create non-root user
RUN groupadd -r shadowlink && useradd -r -g shadowlink -d /app shadowlink

# Create data directories
RUN mkdir -p /app/data/faiss_index /app/data/memory /app/data/uploads /app/logs \
    && chown -R shadowlink:shadowlink /app

# Copy application code
COPY --chown=shadowlink:shadowlink app/ ./app/
COPY --chown=shadowlink:shadowlink proto/ ./proto/

# Switch to non-root user
USER shadowlink

# Environment
ENV SHADOWLINK_ENV=prod \
    SHADOWLINK_LOG_LEVEL=INFO \
    SHADOWLINK_DEBUG=false \
    SHADOWLINK_API_HOST=0.0.0.0 \
    SHADOWLINK_API_PORT=8000 \
    SHADOWLINK_GRPC_PORT=50051 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Expose ports: REST API + gRPC
EXPOSE 8000 50051

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run with uvicorn
CMD ["python", "-m", "uvicorn", "app.main:app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "2", "--log-level", "info"]
