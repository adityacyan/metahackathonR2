FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

# Runtime env vars with defaults (override via docker run -e or HF Space secrets)
ENV PORT=7860
ENV HOST=0.0.0.0
ENV ENVIRONMENT=production

WORKDIR /app

# Install dependencies first for better Docker layer caching.
COPY server/requirements.txt /tmp/requirements.txt
RUN python -m pip install --upgrade pip && \
    pip install -r /tmp/requirements.txt

# Copy project source.
COPY . /app

# HF Spaces requires port 7860
EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:7860/docs', timeout=5)" || exit 1

CMD ["sh", "-c", "uvicorn server.app:app --host 0.0.0.0 --port 7860"]
