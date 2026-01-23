# Multi-stage build for Solsbot Helper
# Stage 1: Install dependencies
FROM python:3.13-slim-bookworm AS builder

# Set working directory
WORKDIR /app

# Install build dependencies for compiled packages (asyncmy, aiohttp, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy and install requirements first (better layer caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Stage 2: Runtime image
FROM python:3.13-slim-bookworm AS runtime

# Labels for container metadata
LABEL org.opencontainers.image.title="Solsbot Helper"
LABEL org.opencontainers.image.description="Discord bot for Sol's RNG game notifications"
LABEL org.opencontainers.image.source="https://github.com/your-repo/solsbot-helper"
LABEL org.opencontainers.image.version="1.0.0"

# Create non-root user for security
RUN groupadd --gid 1000 solsbot && \
    useradd --uid 1000 --gid 1000 --shell /bin/bash --create-home solsbot

# Set working directory
WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Required for health checks
    procps \
    # CA certificates for HTTPS connections
    ca-certificates \
    # Timezone data (optional)
    tzdata \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Set environment variables
ENV PATH="/opt/venv/bin:$PATH" \
    # Prevent Python from writing .pyc files
    PYTHONDONTWRITEBYTECODE=1 \
    # Ensure Python output is sent straight to terminal without buffering
    PYTHONUNBUFFERED=1 \
    # Set Python to use UTF-8 encoding
    PYTHONIOENCODING=utf-8 \
    # Disable pip version check
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # Run in production mode
    ENVIRONMENT=production

# Copy application code
COPY --chown=solsbot:solsbot main.py .
COPY --chown=solsbot:solsbot cogs/ ./cogs/
COPY --chown=solsbot:solsbot infrastructure/ ./infrastructure/
COPY --chown=solsbot:solsbot services/ ./services/
COPY --chown=solsbot:solsbot models/ ./models/
COPY --chown=solsbot:solsbot repositories/ ./repositories/

# Switch to non-root user
USER solsbot

# Health check using process detection
# Note: This is a backup to Kubernetes probes
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD pgrep -f "python.*main.py" > /dev/null || exit 1

# Default command - runs the bot with normal INFO logging
# Terminal input (q/r) won't work in K8s, but logs will be visible
CMD ["python", "main.py"]

# Alternative: Run with verbose DEBUG logging for detailed debugging
# CMD ["python", "main.py", "--verbose"]

# Silent mode (disables all logs - not recommended for K8s debugging)
# CMD ["python", "main.py", "--silent"]
