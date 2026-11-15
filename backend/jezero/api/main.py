"""FastAPI application entry point.

    uvicorn jezero.api.main:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from .. import __version__, db
from ..config import get_settings
from . import routes_map, routes_nasa, routes_waypoints
from .state import build_state, get_state


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base = {"ts": self.formatTime(record), "level": record.levelname, "logger": record.name, "msg": record.getMessage()}
        for k in ("request_id", "method", "path", "status", "ms"):
            if hasattr(record, k):
                base[k] = getattr(record, k)
        if record.exc_info:
            base["exc"] = self.formatException(record.exc_info)
        return json.dumps(base)


def _configure_logging(level: str) -> None:
    h = logging.StreamHandler()
    h.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [h]
    root.setLevel(level)


settings = get_settings()
_configure_logging(settings.log_level)
log = logging.getLogger("jezero.api")

if settings.sentry_dsn:
    import sentry_sdk

    sentry_sdk.init(dsn=settings.sentry_dsn, environment=settings.environment, traces_sample_rate=0.05,
                    send_default_pii=False)


@asynccontextmanager
async def lifespan(app: FastAPI):
    build_state(settings)
    db.init(settings.database_path)
    log.info("startup complete", extra={"path": str(settings.processed_dir)})
    yield
    get_state().nasa.close()
    db.close()


app = FastAPI(title="Jezero Delta Explorer API", version=__version__, lifespan=lifespan,
              docs_url="/api/docs", redoc_url=None, openapi_url="/api/openapi.json")
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins), allow_credentials=False,
                   allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
                   allow_headers=["Content-Type", "If-None-Match", "X-Workspace-Key"], max_age=600)


@app.middleware("http")
async def access_log(request: Request, call_next):
    rid = request.headers.get("cf-ray") or uuid.uuid4().hex[:16]
    t0 = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        log.exception("unhandled error", extra={"request_id": rid, "method": request.method, "path": request.url.path})
        return JSONResponse({"detail": "Internal server error", "request_id": rid}, status_code=500)
    ms = round((time.perf_counter() - t0) * 1000, 1)
    response.headers["X-Request-ID"] = rid
    response.headers["Server-Timing"] = f"app;dur={ms}"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if not request.url.path.startswith("/api/v1/tiles/"):
        log.info("request", extra={"request_id": rid, "method": request.method, "path": request.url.path,
                                   "status": response.status_code, "ms": ms})
    return response


@app.get("/healthz", include_in_schema=False)
def healthz() -> dict:
    return {"status": "ok", "version": __version__}


@app.get("/readyz", include_in_schema=False)
def readyz() -> JSONResponse:
    st = get_state()
    ok_db = db.ping()
    ok_layers = all(st.catalog.available(layer.id) for layer in st.catalog.layers())
    body = {"database": ok_db, "rasters": ok_layers, "layers": len(st.catalog.layers()),
            "catalog_version": st.catalog.version}
    return JSONResponse(body, status_code=200 if ok_db and ok_layers else 503)


app.include_router(routes_map.router)
app.include_router(routes_waypoints.router)
app.include_router(routes_nasa.router)
