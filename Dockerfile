# Multi-stage build for MAOS
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN pip install --no-cache-dir hatchling

# Copy project files
COPY pyproject.toml README.md ./
COPY maos/ maos/

# Build wheel
RUN pip wheel --no-deps --wheel-dir /wheels .

# Runtime stage
FROM python:3.11-slim AS runtime

WORKDIR /app

# Create non-root user
RUN groupadd -r maos && useradd -r -g maos maos

# Install runtime dependencies
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/*.whl && rm -rf /wheels

# Copy config (users mount their own)
COPY .env.example .env.example

# Switch to non-root user
USER maos

# Expose API port
EXPOSE 7777

# Health check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:7777/health')" || exit 1

# Default command
ENTRYPOINT ["maos"]
CMD ["serve", "-c", "/app/config/config.yaml"]
