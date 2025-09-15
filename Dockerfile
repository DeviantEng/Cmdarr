# Use Python 3.13 slim image
FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Default PUID/PGID (can be overridden at runtime)
ENV PUID=1000
ENV PGID=1000

# Default application settings
ENV WEB_HOST=0.0.0.0
ENV WEB_PORT=8080
ENV LOG_LEVEL=INFO
ENV LOG_RETENTION_DAYS=7

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    gosu \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

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
