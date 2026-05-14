# Stage 1: Build React frontend
FROM node:24-trixie-slim@sha256:4f2b45e32dc7d2caf66b6dbd59fac50e32f8077769efe0ef4d4c3f114672537d AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Python application
FROM python:3.14-slim-trixie@sha256:1697e8e8d39bf168e177ac6b5fdab6df86d81cfc24dae17dfb96cfc3ef76b4dd

ARG IMAGE_TAG=latest
ENV CMDARR_IMAGE_TAG=${IMAGE_TAG}

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Default PUID/PGID (can be overridden at runtime)
ENV PUID=1000 \
    PGID=1000

# Default application settings
ENV WEB_HOST=0.0.0.0 \
    WEB_PORT=8080 \
    LOG_LEVEL=INFO \
    LOG_RETENTION_DAYS=7

# Install system dependencies
RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    curl \
    gosu \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Copy built frontend from builder stage
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Create app user for security (will be modified at runtime if needed)
RUN groupadd -r -g 1000 appuser && useradd -r -u 1000 -g appuser appuser

# Create data directory and set ownership
RUN mkdir -p /app/data/logs && \
    chown -R appuser:appuser /app/data

# Copy entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD gosu appuser curl -f http://localhost:8080/health || exit 1

# Use entrypoint script to handle UID/GID changes at runtime
ENTRYPOINT ["/entrypoint.sh"]

# Default command runs FastAPI server
CMD ["python", "run_fastapi.py"]
