# brandOS Autonomous Loop Container
# Runs the main loop 24/7 for continuous brand intelligence

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy project files
COPY pyproject.toml ./
COPY src/ ./src/

# Install dependencies
RUN uv pip install --system -e ".[agents,workflows,notifications]"

# Copy brand configurations
COPY brands/ ./brands/

# Create data directory
RUN mkdir -p /data/brandos

# Environment
ENV BRANDOPS_DATA_DIR=/data/brandos
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "from brand_os.loop import LoopState; print('ok')" || exit 1

# Run the loop
ENTRYPOINT ["python", "-m", "brand_os.loop"]
