# Stage 1: Build dependencies
FROM python:3.11-slim AS builder

WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install system dependencies required for build
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies in a virtualenv to easily copy later
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt gunicorn

# Stage 2: Runtime
FROM python:3.11-slim

# Create a non-root user
RUN groupadd -r cloudvault && useradd -r -g cloudvault cloudvault

WORKDIR /app

# Install runtime dependencies (e.g., for sqlite or postgres)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy virtualenv from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY . .

# Ensure instance directory exists for SQLite & Backups with correct permissions
RUN mkdir -p instance/backups && \
    chown -R cloudvault:cloudvault /app

# Switch to non-root user
USER cloudvault

# Expose port
EXPOSE 5000

# Healthcheck
#HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  #CMD curl -f http://localhost:5000/health || exit 1

# Start Gunicorn
CMD ["gunicorn", "-c", "gunicorn.conf.py", "run:app"]
