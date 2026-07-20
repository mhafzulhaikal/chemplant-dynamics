# ── Stage 1: builder ──────────────────────────────────────────────────────────
# Uses uv's official slim image so we get uv without an extra pip install step.
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder

WORKDIR /app

# Enable uv's bytecode compilation and link mode for faster cold-starts.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Copy only the dependency manifests first (layer-cache friendly).
COPY pyproject.toml uv.lock ./

# Install production dependencies into /app/.venv.
# --frozen:             honour the exact lock-file — no implicit upgrades.
# --no-dev:             skip development-only dependencies.
# --no-install-project: don't try to install the project itself as a package.
RUN uv sync --frozen --no-dev --no-install-project

# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM python:3.13-slim AS runtime

WORKDIR /app

# Copy the pre-built virtual environment from the builder stage.
COPY --from=builder /app/.venv /app/.venv

# Copy application source (everything not excluded by .dockerignore).
COPY . .

# Put the venv's binaries first on PATH.
ENV PATH="/app/.venv/bin:$PATH" \
    # Flush stdout/stderr immediately so logs appear in real time.
    PYTHONUNBUFFERED=1 \
    # Prevent Python from writing .pyc files at runtime (already compiled above).
    PYTHONDONTWRITEBYTECODE=1

# Create directories that may be bind-mounted at runtime.
RUN mkdir -p /app/data /app/logs

EXPOSE 8080

# Lightweight health-check — waits for the NiceGUI HTTP server to respond.
# --start-period gives the app time to boot before the first probe counts.
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

# NiceGUI recommends running via `python app/main.py` (uses uvicorn internally).
# Use the JSON (exec-form) so that PID 1 is the Python process — signals work correctly.
CMD ["python", "app/main.py"]
