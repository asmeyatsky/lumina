# =============================================================================
# LUMINA Backend — Multi-stage Dockerfile
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1: builder — install Python dependencies with uv
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install uv (fast Python package installer)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /build

# Copy dependency manifests first for layer caching
COPY pyproject.toml uv.lock ./

# Install production dependencies into a virtual environment
RUN uv venv /opt/venv && \
    uv pip install --python /opt/venv/bin/python --no-cache -r pyproject.toml

# ---------------------------------------------------------------------------
# Stage 2: runtime — lean production image
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

# Security: run as non-root
RUN groupadd --gid 1001 lumina && \
    useradd --uid 1001 --gid lumina --shell /bin/false --create-home lumina

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Copy application source
COPY src/ ./src/
COPY pyproject.toml ./

# Install the project itself (editable-style so lumina package is importable)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
RUN uv pip install --python /opt/venv/bin/python --no-cache -e .

# Drop back to non-root
USER lumina

EXPOSE 8000

# Health check — hit the /health endpoint every 30s
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "lumina.presentation.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
