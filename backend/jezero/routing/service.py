"""Route planning service: raster windows → cost grid → A* → statistics.

Terrain sources
  ctx        CTX DEM, 20 m — regional baseline covering the whole delta.
  hirise_1/2 HiRISE DTM at its processed (~1 m) resolution; usable only where
             that DTM has data. Cells outside its footprint are NoData and
             therefore impassable — the route is never silently bridged.
  auto       HiRISE when both endpoints are inside one HiRISE footprint and
             the corridor fits the cell budget; otherwise CTX.

The DEM window is read at native resolution (no overviews) with a 1-pixel
halo so slope/TRI are identical to the published derivative rasters.
"""
from __future__ import annotations

import math
import os
from dataclasses import dataclass
from typing import Any

from rasterio.windows import Window

from .. import terrain
from ..crs import Boundary, MarsEquirectangular
from ..raster.catalog import Catalog
from .astar import BlockedEndpointError, NoRouteError, astar
from .cost import CostProfile, build_edge_weights
from .stats import route_stats

DEM_LAYERS = {"ctx": "ctx_dem", "hirise_1": "hirise_dtm_1", "hirise_2": "hirise_dtm_2"}

LIMITATIONS = (
    "Terrain-cost path estimate only — NOT a certified safe route. Costs use orbital DEM slope, "
    "grade and roughness at the stated resolution; hazards smaller than a few DEM pixels (rocks, "
    "ripples, sand traps) are not resolved. Profile thresholds are planning parameters, not rover "
    "mobility limits."
)


class RouteRequestError(ValueError):
    """Invalid request (outside boundary, unknown profile/source, too large)."""


@dataclass
class Window2D:
    row0: int
    col0: int
    rows: int
    cols: int


class RouteService:
    def __init__(self, catalog: Catalog, crs: MarsEquirectangular, boundary: Boundary, routing_cfg: dict):
        self.catalog = catalog
        self.crs = crs
        self.boundary = boundary
        self.cfg = routing_cfg
        self.profiles = {n: CostProfile.from_config(n, p) for n, p in routing_cfg["profiles"].items()}
        # ≈180 B of RAM per cell: 1.5 M cells ≈ 330 MB peak (fits a 512 MB free instance).
        # Hosts with more memory can raise it with JEZERO_ROUTE_MAX_CELLS.
        env_cells = os.environ.get("JEZERO_ROUTE_MAX_CELLS")
        self.max_cells = int(env_cells) if env_cells else int(routing_cfg.get("max_window_cells", 1_500_000))

    # ----------------------------------------------------------------- helpers
    def _valid_at(self, layer_id: str, x: float, y: float) -> bool:
        if layer_id not in self.catalog:
            return False
        layer = self.catalog.get(layer_id)
        if not layer.contains(x, y):
            return False
        src = self.catalog.open(layer_id)
        r, c = src.index(x, y)
        if not (0 <= r < src.height and 0 <= c < src.width):
            return False
        return bool(src.dataset_mask(window=Window(c, r, 1, 1))[0, 0])

    def _choose_source(self, requested: str, a, b) -> str:
        if requested != "auto":
            if requested not in DEM_LAYERS or DEM_LAYERS[requested] not in self.catalog:
                raise RouteRequestError(f"Terrain source '{requested}' is not available")
            return requested
        for key in ("hirise_1", "hirise_2"):
            lid = DEM_LAYERS[key]
            if self._valid_at(lid, *a) and self._valid_at(lid, *b):
                if self._corridor(lid, a, b, full=False)[1] <= self.max_cells:
                    return key
        return "ctx"

    def _corridor(self, lid: str, a, b, full: bool) -> tuple[Window2D, int]:
        src = self.catalog.open(lid)
        if full:
            w = Window2D(0, 0, src.height, src.width)
            return w, w.rows * w.cols
        d = math.hypot(b[0] - a[0], b[1] - a[1])
        margin = max(float(self.cfg.get("corridor_margin_m", 1500)), float(self.cfg.get("corridor_margin_fraction", 0.5)) * d)
        x0, x1 = min(a[0], b[0]) - margin, max(a[0], b[0]) + margin
        y0, y1 = min(a[1], b[1]) - margin, max(a[1], b[1]) + margin
        r0, c0 = src.index(x0, y1)
        r1, c1 = src.index(x1, y0)
        r0, c0 = max(r0, 0), max(c0, 0)
        r1, c1 = min(r1 + 1, src.height), min(c1 + 1, src.width)
        w = Window2D(r0, c0, r1 - r0, c1 - c0)
        return w, w.rows * w.cols

    def _read(self, lid: str, w: Window2D):
        src = self.catalog.open(lid)
        rr0, cc0 = max(w.row0 - 1, 0), max(w.col0 - 1, 0)
        rr1, cc1 = min(w.row0 + w.rows + 1, src.height), min(w.col0 + w.cols + 1, src.width)
        win = Window(cc0, rr0, cc1 - cc0, rr1 - rr0)
        z = terrain.to_float_with_nan(src.read(1, window=win), src.nodata, src.read_masks(1, window=win) > 0)
        res_x, res_y = src.res
        if abs(res_x - res_y) > 1e-6 * res_x:
            raise RouteRequestError("Routing requires square DEM pixels")
        s = terrain.slope_degrees(z, res_x, res_y)
        r = terrain.tri_riley(z)
        crop = (slice(w.row0 - rr0, w.row0 - rr0 + w.rows), slice(w.col0 - cc0, w.col0 - cc0 + w.cols))
        return z[crop], s[crop], r[crop], float(res_x)

    # -------------------------------------------------------------------- API
    def plan(self, start_xy: tuple[float, float], goal_xy: tuple[float, float],
             profile: str | None = None, terrain_source: str = "auto") -> dict[str, Any]:
        for name, (x, y) in (("start", start_xy), ("destination", goal_xy)):
            if not (math.isfinite(x) and math.isfinite(y)):
                raise RouteRequestError(f"{name} coordinates must be finite")
            if not self.boundary.contains(x, y):
                raise RouteRequestError(f"{name} is outside the Jezero project boundary")
        pname = profile or self.cfg.get("default_profile", "balanced")
        if pname not in self.profiles:
            raise RouteRequestError(f"Unknown profile '{pname}'")
        prof = self.profiles[pname]
        key = self._choose_source(terrain_source, start_xy, goal_xy)
        lid = DEM_LAYERS[key]
        if lid not in self.catalog:
            raise RouteRequestError(f"Terrain layer {lid} is not available")
        for name, pt in (("start", start_xy), ("destination", goal_xy)):
            if not self._valid_at(lid, *pt):
                raise BlockedEndpointError(f"{name} has no {self.catalog.get(lid).title} elevation data (NoData)")

        attempts = []
        for full in (False, True):
            w, cells = self._corridor(lid, start_xy, goal_xy, full=full)
            if cells > self.max_cells:
                if full:
                    raise NoRouteError(
                        "No route found inside the search corridor, and a search of the whole "
                        f"{self.catalog.get(lid).title} extent exceeds the cell budget. Try the CTX 20 m source.")
                raise RouteRequestError(
                    f"Corridor needs {cells:,} cells at {self.catalog.get(lid).resolution_m:.2f} m "
                    f"(limit {self.max_cells:,}). Choose closer points or the CTX 20 m terrain source.")
            z, s, r, res = self._read(lid, w)
            edges = build_edge_weights(z, s, res, prof, rough=r)
            src = self.catalog.open(lid)
            sr, sc = src.index(*start_xy)
            gr, gc = src.index(*goal_xy)
            start = (sr - w.row0, sc - w.col0)
            goal = (gr - w.row0, gc - w.col0)
            try:
                result = astar(edges, start, goal)
            except NoRouteError as exc:
                attempts.append({"window": [w.row0, w.col0, w.rows, w.cols], "result": str(exc)})
                if full or (w.rows == src.height and w.cols == src.width):
                    raise NoRouteError(
                        f"No traversable route under the '{prof.label}' profile on {self.catalog.get(lid).title}: "
                        "steep or NoData terrain separates the points. Try a less restrictive profile or another "
                        "terrain source.") from None
                continue
            break
        else:  # pragma: no cover - loop always breaks or raises
            raise NoRouteError("No route found")

        stats = route_stats(result.path, z, s, edges)
        width = w.cols
        coords, lonlat = [], []
        for p in result.path:
            rr, cc = divmod(p, width)
            x, y = src.xy(rr + w.row0, cc + w.col0)
            coords.append([x, y])
            lon, lat = self.crs.inverse(x, y)
            lonlat.append([lon, lat])
        layer = self.catalog.get(lid)
        return {
            "label": "Terrain-cost path estimate (not a certified safe route)",
            "geometry": {"type": "LineString", "coordinates": coords, "crs": f"{self.crs.crs_id}@v{self.crs.version}"},
            "geographic": lonlat,
            "stats": stats.as_dict(),
            "terrain": {"source": key, "layer": lid, "title": layer.title, "resolution_m": res,
                        "window": {"row0": w.row0, "col0": w.col0, "rows": w.rows, "cols": w.cols},
                        "auto_selected": terrain_source == "auto"},
            "profile": prof.as_dict(),
            "search": {"expansions": result.expansions, "retries": attempts,
                       "algorithm": "A* (8-neighbour, octile heuristic, no corner cutting)"},
            "limitations": LIMITATIONS,
        }
