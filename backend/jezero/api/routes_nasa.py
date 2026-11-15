"""Mars 2020 Perseverance raw-image gallery endpoints (proxy of NASA's public feed)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.concurrency import run_in_threadpool

from ..nasa_raw import Query as RawQuery
from ..nasa_raw import UpstreamError, camera_groups
from .state import AppState, get_state

router = APIRouter(prefix="/api/v1/raw-images", tags=["nasa"])


@router.get("/cameras")
def cameras(response: Response) -> dict:
    response.headers["Cache-Control"] = "public, max-age=86400"
    return {"cameras": camera_groups()}


@router.get("")
async def raw_images(
    response: Response,
    page: int = Query(0, ge=0, le=10_000),
    per_page: int = Query(24, ge=1, le=50),
    sol_min: int | None = Query(None, ge=0, le=20_000),
    sol_max: int | None = Query(None, ge=0, le=20_000),
    camera: str | None = Query(None, max_length=32, pattern=r"^[a-z_]+$"),
    order: str = Query("desc", pattern=r"^(asc|desc)$"),
    st: AppState = Depends(get_state),
) -> dict:
    try:
        q = RawQuery(page, per_page, sol_min, sol_max, camera, order).validate()
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    try:
        result = await run_in_threadpool(st.nasa.fetch, q)
    except UpstreamError as exc:
        raise HTTPException(502, str(exc)) from None
    response.headers["Cache-Control"] = f"public, max-age={min(st.settings.nasa_cache_seconds, 600)}"
    return result
