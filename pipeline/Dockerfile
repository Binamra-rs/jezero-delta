# Pipeline image — full GDAL CLI + Python bindings
FROM ghcr.io/osgeo/gdal:ubuntu-full-3.9.3

# Disable inherited unsigned/unverified Apache Arrow repository
RUN mv /etc/apt/sources.list.d/apache-arrow.sources \
       /etc/apt/sources.list.d/apache-arrow.sources.disabled

# Install Python tooling
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        python3-venv \
        python3-pip && \
    rm -rf /var/lib/apt/lists/* && \
    python3 -m venv --system-site-packages /venv

ENV PATH=/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    JEZERO_DATA_DIR=/data \
    JEZERO_PROJECT_CONFIG=/repo/config/project.yaml

WORKDIR /repo

COPY backend/requirements.txt backend/requirements-pipeline.txt backend/

RUN pip install --no-cache-dir -r backend/requirements-pipeline.txt

COPY backend backend
COPY pipeline pipeline
COPY config config

ENTRYPOINT ["bash", "pipeline/run_all.sh"]