"""Map, raster, inspection and routing endpoints (public, read-only)."""
from __future__ import annotations

import hashlib

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.concurrency import run_in_threadpool

from ..crs import CoordinateError
from ..raster import colormap, sampler, tiles
from ..raster.catalog import UnknownLayerError
from ..ratelimit import client_ip
from ..routing.astar import BlockedEndpointError, NoRouteError
from ..routing.service import DEM_LAYERS, RouteRequestError
from ..tilegrid import TileIndexError
from .schemas import Point, RouteRequest
from .state import AppState, get_state

router = APIRouter(prefix="/api/v1", tags=["map"])


def to_xy(st: AppState, p: Point) -> tuple[float, float]:
    try:
        if p.x is not None:
            st.crs.inverse(p.x, p.y)  # validates domain
            return float(p.x), float(p.y)
        return st.crs.forward(float(p.lon_e), float(p.lat))
    except CoordinateError as exc:
        raise HTTPException(422, str(exc)) from None


def location_block(st: AppState, x: float, y: float) -> dict:
    lon, lat = st.crs.inverse(x, y)
    return {"x": x, "y": y, "lon_e": lon, "lat": lat, "crs_id": st.crs.crs_id, "crs_version": st.crs.version,
            "inside_boundary": st.boundary.contains(x, y)}


@router.get("/config")
def project_config(response: Response, st: AppState = Depends(get_state)) -> dict:
    response.headers["Cache-Control"] = "public, max-age=300"
    layers = []
    for layer in st.catalog.layers():
        meta = layer.public()
        ramp = tiles.STYLE_RAMP.get(layer.style, "gray")
        meta["legend"] = {"ramp": ramp, "stops": colormap.legend(ramp), "range": layer.range}
        layers.append(meta)
    return {
        "project": st.project["project"],
        "crs": st.crs.describe(),
        "boundary": list(st.boundary.bounds),
        "tilegrid": st.grid.describe(),
        "catalog_version": st.catalog.version,
        "layers": layers,
        "routing": {
            "default_profile": st.project["routing"].get("default_profile"),
            "profiles": {k: p.as_dict() for k, p in st.router.profiles.items()},
            "terrain_sources": ["auto"] + [k for k, lid in DEM_LAYERS.items() if lid in st.catalog],
        },
        "raw_images": {"sol_presets": (st.project.get("raw_images") or {}).get("sol_presets") or []},
    }


@router.get("/layers/{layer_id}/coverage")
def coverage(layer_id: str, response: Response, st: AppState = Depends(get_state)) -> Response:
    try:
        path = st.catalog.coverage_path(layer_id)
    except UnknownLayerError:
        raise HTTPException(404, "Unknown layer") from None
    if path is None:
        raise HTTPException(404, "No coverage footprint for this layer")
    return Response(path.read_bytes(), media_type="application/geo+json",
                    headers={"Cache-Control": "public, max-age=86400"})


@router.get("/tiles/{layer_id}/{z}/{x}/{y}.png")
async def tile(layer_id: str, z: int, x: int, y: int, request: Request, st: AppState = Depends(get_state)) -> Response:
    try:
        layer = st.catalog.get(layer_id)
    except UnknownLayerError:
        raise HTTPException(404, "Unknown layer") from None
    if not layer.path.exists():
        raise HTTPException(404, "Tiles for this layer are not rendered by this API host (served statically)")
    etag = '"' + hashlib.sha1(f"{st.catalog.version}/{layer_id}/{z}/{x}/{y}".encode()).hexdigest() + '"'
    headers = {"Cache-Control": f"public, max-age={st.settings.tile_cache_seconds}", "ETag": etag}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    try:
        png = await run_in_threadpool(tiles.render, st.catalog, st.grid, layer, z, x, y)
    except TileIndexError:
        raise HTTPException(404, "Tile outside the project tile matrix") from None
    return Response(png, media_type="image/png", headers=headers)


@router.get("/inspect")
async def inspect(x: float | None = Query(None), y: float | None = Query(None),
                  lon_e: float | None = Query(None), lat: float | None = Query(None, ge=-90, le=90),
                  st: AppState = Depends(get_state)) -> dict:
    try:
        p = Point(x=x, y=y, lon_e=lon_e, lat=lat)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    px, py = to_xy(st, p)
    loc = location_block(st, px, py)
    if not loc["inside_boundary"]:
        raise HTTPException(422, "Location is outside the Jezero project boundary")
    result = await run_in_threadpool(sampler.inspect, st.catalog, px, py)
    return {"location": loc, **result}


@router.post("/route")
async def route(req: RouteRequest, request: Request, st: AppState = Depends(get_state)) -> dict:
    st.route_limiter.check("route:" + client_ip(request))
    a, b = to_xy(st, req.start), to_xy(st, req.end)
    try:
        result = await run_in_threadpool(st.router.plan, a, b, req.profile, req.terrain_source)
    except (RouteRequestError, BlockedEndpointError) as exc:
        raise HTTPException(422, str(exc)) from None
    except NoRouteError as exc:
        raise HTTPException(409, str(exc)) from None
    result["start"] = location_block(st, *a)
    result["end"] = location_block(st, *b)
    return result


@router.get("/convert")
def convert(x: float | None = None, y: float | None = None, lon_e: float | None = None,
            lat: float | None = Query(None, ge=-90, le=90), st: AppState = Depends(get_state)) -> dict:
    try:
        p = Point(x=x, y=y, lon_e=lon_e, lat=lat)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    return location_block(st, *to_xy(st, p))

