# syntax=docker/dockerfile:1

# =============================================================================
# Builder: install Python dependencies into a virtualenv
# =============================================================================
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# =============================================================================
# Runtime
# =============================================================================
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    APP_PORT=8000 \
    CHROMA_PERSIST_DIR=/data/chroma \
    RUN_MIGRATIONS=true \
    SEED_DEMO_DATA=false

RUN groupadd --system app && useradd --system --gid app --home-dir /app app \
    && mkdir -p /data/chroma && chown -R app:app /data

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY --chown=app:app . .
RUN chmod +x docker/entrypoint.sh

USER app
VOLUME ["/data/chroma"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"APP_PORT\", \"8000\")}/api/v1/health', timeout=4)" || exit 1

ENTRYPOINT ["docker/entrypoint.sh"]
# Single worker: replay runs and background evaluations live in-process,
# and the embedded Chroma store is not safe across multiple processes.
CMD ["sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port ${APP_PORT} --proxy-headers --forwarded-allow-ips='*'"]
