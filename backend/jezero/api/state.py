"""Application state assembled once at startup."""
from __future__ import annotations

from dataclasses import dataclass

from ..config import Settings, load_project_config
from ..crs import Boundary, MarsEquirectangular
from ..nasa_raw import RawImageClient
from ..raster.catalog import Catalog
from ..ratelimit import RateLimiter
from ..routing.service import RouteService
from ..tilegrid import TileGrid


@dataclass
class AppState:
    settings: Settings
    project: dict
    crs: MarsEquirectangular
    boundary: Boundary
    grid: TileGrid
    catalog: Catalog
    router: RouteService
    nasa: RawImageClient
    route_limiter: RateLimiter
    write_limiter: RateLimiter


_state: AppState | None = None


def build_state(settings: Settings) -> AppState:
    global _state
    cfg = load_project_config()
    crs = MarsEquirectangular.from_config(cfg["crs"])
    boundary = Boundary.from_config(cfg["boundary"], crs)
    # only layers still declared in project.yaml are served, even if catalog.json lists more
    catalog = Catalog(settings.processed_dir, {layer["id"] for layer in cfg["layers"]})
    # the catalog must have been built for exactly this CRS and boundary
    if abs(float(catalog.crs["standard_parallel_deg"]) - crs.lat_ts_deg) > 1e-12 or \
       abs(float(catalog.crs["central_meridian_deg_e"]) - crs.lon0_deg) > 1e-12 or \
       int(catalog.crs["version"]) != crs.version:
        raise RuntimeError("processed/catalog.json was built for a different project CRS; re-run the pipeline")
    if any(abs(a - b) > 1e-6 for a, b in zip(catalog.boundary, boundary.bounds, strict=True)):
        raise RuntimeError("processed/catalog.json was built for a different boundary; re-run the pipeline")
    t = cfg["tiles"]
    grid = TileGrid.build(boundary, int(t.get("tile_size_px", 256)), float(t.get("finest_resolution_m", 0.5)))
    nasa = RawImageClient(settings.nasa_raw_api_url, settings.nasa_timeout_seconds, settings.nasa_cache_seconds)
    _state = AppState(settings, cfg, crs, boundary, grid, catalog,
                      RouteService(catalog, crs, boundary, cfg["routing"]), nasa,
                      RateLimiter(settings.route_rate_per_minute), RateLimiter(settings.write_rate_per_minute))
    return _state


def get_state() -> AppState:
    if _state is None:
        raise RuntimeError("Application state not initialised")
    return _state
