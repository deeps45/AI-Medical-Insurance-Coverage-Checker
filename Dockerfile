FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    API_PORT=8000 \
    STREAMLIT_PORT=8501 \
    FAISS_DIR=/app/data/faiss \
    TESSERACT_CMD=/usr/bin/tesseract \
    USE_LOCAL_VECTORSTORE=true \
    USE_NGINX=true

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    poppler-utils \
    tesseract-ocr \
    libgl1 \
    libglib2.0-0 \
    gcc \
    curl \
    nginx \
    && rm -rf /var/lib/apt/lists/* \
    && rm -f /etc/nginx/sites-enabled/default

COPY backend/requirements.txt ./backend/
COPY frontend/requirements.txt ./frontend/

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=100
RUN pip install --no-cache-dir --prefer-binary -r backend/requirements.txt \
    && pip install --no-cache-dir --prefer-binary -r frontend/requirements.txt

COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY deploy/nginx.conf ./deploy/nginx.conf
COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh \
    && mkdir -p /app/data/faiss /var/cache/nginx /var/log/nginx /var/run

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD curl -sf "http://127.0.0.1:${PORT:-8080}/health" || exit 1

CMD ["/app/docker-entrypoint.sh"]
