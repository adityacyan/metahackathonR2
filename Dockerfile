FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY server/requirements.txt /tmp/requirements.txt

# Install Python dependencies
RUN python -m pip install --upgrade pip && \
    pip install -r /tmp/requirements.txt

# Copy all source code
COPY . /app

# Set Python path to include current directory
ENV PYTHONPATH=/app

# HF Spaces uses port 7860
EXPOSE 7860

# Simple healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:7860/docs || exit 1

# Start the server with better error handling
CMD ["python", "startup.py"]
