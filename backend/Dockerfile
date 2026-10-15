# ==============================================================================
# AERIS Backend - Production Multi-Stage Dockerfile
# ==============================================================================

# Stage 1: Build & Dependencies
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install --no-install-recommends -y \
    build-essential \
    libpq-dev \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: Minimal Runtime Image
FROM python:3.11-slim AS runtime

WORKDIR /app

# Install system libraries required by OpenCV headless and cryptographic libraries
RUN apt-get update && apt-get install --no-install-recommends -y \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    curl \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Create non-root application user for defense-in-depth container security
RUN groupadd -g 1001 aerisgroup && \
    useradd -u 1001 -g aerisgroup -m -s /bin/bash aerisuser

# Create persistent storage directories
RUN mkdir -p /app/data /app/backups && \
    chown -R aerisuser:aerisgroup /app

# Copy application source code
COPY --chown=aerisuser:aerisgroup . /app

# Switch to non-privileged user
USER aerisuser

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ENVIRONMENT=production \
    DATABASE_URL="sqlite:////app/data/aeris.db"

# Expose internal service port
EXPOSE 8000 10000

# Container healthcheck using liveness probe
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health/live || exit 1

# Start Uvicorn ASGI server with single worker for Render 512MB free tier
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --proxy-headers --forwarded-allow-ips '*'"]
