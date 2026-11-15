# API image — FastAPI + rasterio (wheels bundle GDAL). Serves tiles, inspect, routing, waypoints.
FROM python:3.12-slim AS api

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    GDAL_CACHEMAX=512 GDAL_DISABLE_READDIR_ON_OPEN=EMPTY_DIR VSI_CACHE=TRUE VSI_CACHE_SIZE=67108864

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/* \
 && useradd --system --uid 10001 --home /app jezero

WORKDIR /app
COPY backend/requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

COPY backend/jezero ./jezero
COPY backend/scripts ./scripts
COPY config /config

ENV JEZERO_PROJECT_CONFIG=/config/project.yaml JEZERO_DATA_DIR=/data JEZERO_DB_PATH=/state/jezero.sqlite3
RUN mkdir -p /state && chown jezero /state
USER jezero
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD curl -fsS http://127.0.0.1:8000/healthz || exit 1
CMD ["gunicorn", "jezero.api.main:app", "-k", "uvicorn.workers.UvicornWorker", "-w", "4", \
     "-b", "0.0.0.0:8000", "--timeout", "120", "--graceful-timeout", "30", "--access-logfile", "-"]
