# LinkedIn Prospecting Agents - Dockerfile
# ========================================

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for better caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY *.py ./
COPY config.yaml ./

# Create directories for data persistence
RUN mkdir -p leads state logs

# Set proper permissions
RUN chmod +x *.py

# Health check
HEALTHCHECK --interval=60s --timeout=30s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

# Default command (can be overridden)
CMD ["python", "cli.py", "--help"]

# Labels for container metadata
LABEL maintainer="Your Name <your.email@example.com>"
LABEL version="1.0.0"
LABEL description="LinkedIn Prospecting AI Agents Pipeline"
