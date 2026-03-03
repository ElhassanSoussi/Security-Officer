# Production-grade Backend Dockerfile
# Multi-stage build — slim image, non-root user, no dev dependencies

# ── Stage 1: Install dependencies ──────────────────────────────────────────────
FROM python:3.11-slim-bookworm AS deps

RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: Production image ──────────────────────────────────────────────────
FROM python:3.11-slim-bookworm AS production

# Security: run as non-root user
RUN groupadd --system app && useradd --system --gid app --create-home app

# Patch OS-level vulnerabilities
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy pre-built dependencies from deps stage
COPY --from=deps /install /usr/local

# Copy application code only
COPY app/ ./app/

# Remove unnecessary files that might have leaked
RUN find /app -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true && \
    find /app -name "*.pyc" -delete 2>/dev/null || true

# Set environment
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ENVIRONMENT=production

EXPOSE 8000

# Healthcheck against liveness endpoint (always 200, no deps)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT:-8000}/health/ping')" || exit 1

# Run as non-root
USER app

# Production: use multiple workers, no reload, access log
# Render injects $PORT at runtime; default to 8000 for Docker / local
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2 --access-log
