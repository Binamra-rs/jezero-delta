# API image for free hosts (Render free web service, or any Docker host).
# Build context = repository root. The processed rasters are not in git: they
# are downloaded at build time from JEZERO_DATA_URL (a tar made by
# backend/scripts/make_api_bundle.py, e.g. attached to a GitHub Release).
#
#   docker build -f deploy/render/Dockerfile --build-arg JEZERO_DATA_URL=https://… -t jezero-api .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    GDAL_CACHEMAX=64 GDAL_DISABLE_READDIR_ON_OPEN=EMPTY_DIR

RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates libexpat1 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

# Data layer first so code changes don't re-download it.
ARG JEZERO_DATA_URL
RUN test -n "$JEZERO_DATA_URL" || { echo "JEZERO_DATA_URL is not set (URL of jezero-api-data.tar)"; exit 1; } \
 && mkdir -p /data \
 && curl -fsSL --retry 5 --retry-delay 5 "$JEZERO_DATA_URL" | tar -x -C /data \
 && test -f /data/processed/catalog.json && du -sh /data/processed

COPY backend/jezero ./jezero
COPY config /config

# Free hosts have no persistent disk: the SQLite file is scratch. The hosted
# frontend keeps waypoints in the browser instead (VITE_WAYPOINTS=local).
ENV JEZERO_PROJECT_CONFIG=/config/project.yaml JEZERO_DATA_DIR=/data JEZERO_DB_PATH=/tmp/jezero.sqlite3 \
    JEZERO_ENV=production

RUN useradd --system --uid 10001 jezero
USER jezero
EXPOSE 8000
# One worker: the free instance has 512 MB RAM.
CMD ["sh", "-c", "exec uvicorn jezero.api.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --proxy-headers --forwarded-allow-ips='*'"]
