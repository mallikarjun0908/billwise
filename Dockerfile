# Stage 1: Build & Dependencies
FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# Stage 2: Production Lean Runtime
FROM python:3.12-slim AS runtime

# System runtime dependencies: Tesseract OCR engine + English language pack + curl for healthchecks + libpq5
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    curl \
    libpq5 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Security: Non-root user
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /bin/sh -d /app appuser

WORKDIR /app

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Copy application backend and tariffs
COPY backend/ /app/
COPY tariffs/ /app/tariffs/

# Ensure runtime directories exist with correct permissions
RUN mkdir -p /app/uploads /tmp/billwise && \
    chown -R appuser:appgroup /app /tmp/billwise

# Environment variables:
# Cloud Run sets PORT (default 8080).
# Python unbuffered ensures container logs stream immediately.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

EXPOSE 8080

# Switch to non-root user
USER appuser

# Container healthcheck for Cloud Run / Docker
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Launch uvicorn with exec so SIGTERM is handled gracefully by PID 1
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
