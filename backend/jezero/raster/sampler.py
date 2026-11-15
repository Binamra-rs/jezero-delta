"""Point sampling of native raster values (brief §8).

Sampling method: NEAREST — the value of the native-resolution pixel that
contains the clicked point (overviews are never used). No interpolation, so
every number shown is an actual pixel value of the processed raster. Outside
a layer's valid footprint the result is explicitly "no_data".
"""
from __future__ import annotations

from typing import Any

import numpy as np
from rasterio.windows import Window

from .. import terrain
from .catalog import Catalog, Layer

SAMPLING = "nearest (native pixel containing the point; no interpolation)"


def sample_layer(catalog: Catalog, layer: Layer, x: float, y: float) -> dict[str, Any]:
    base = {"layer": layer.id, "title": layer.title, "unit": layer.unit, "kind": layer.kind,
            "source_dataset": layer.source_dataset, "source_title": layer.meta.get("source_title"),
            "resolution_m": layer.resolution_m, "sampling": SAMPLING}
    if not layer.contains(x, y):
        return {**base, "in_coverage": False, "value": None, "status": "outside_extent"}
    if catalog.on_demand(layer.id):
        return _sample_derived(catalog, layer, x, y, base)
    src = catalog.open(layer.id)
    row, col = src.index(x, y)
    if not (0 <= row < src.height and 0 <= col < src.width):
        return {**base, "in_coverage": False, "value": None, "status": "outside_extent"}
    win = Window(col, row, 1, 1)
    val = src.read(1, window=win)[0, 0]
    mask = src.dataset_mask(window=win)[0, 0]
    if mask == 0 or (src.nodata is not None and val == src.nodata) or not np.isfinite(float(val)):
        return {**base, "in_coverage": False, "value": None, "status": "no_data"}
    cx, cy = src.xy(row, col)
    return {**base, "in_coverage": True, "value": float(val), "status": "ok",
            "pixel": {"row": int(row), "col": int(col), "centre_x": cx, "centre_y": cy}}


def _sample_derived(catalog: Catalog, layer: Layer, x: float, y: float, base: dict) -> dict[str, Any]:
    """Slope / TRI at one pixel, recomputed from the 3×3 DEM neighbourhood.

    Same grid, same algorithm and same NoData rule as pipeline step 04, so the
    value equals the published derivative pixel (stored as float32).
    """
    src = catalog.open(layer.source_dataset)
    row, col = src.index(x, y)
    if not (0 <= row < src.height and 0 <= col < src.width):
        return {**base, "in_coverage": False, "value": None, "status": "outside_extent"}
    r0, c0 = max(row - 1, 0), max(col - 1, 0)
    r1, c1 = min(row + 2, src.height), min(col + 2, src.width)
    win = Window(c0, r0, c1 - c0, r1 - r0)
    z = terrain.to_float_with_nan(src.read(1, window=win), src.nodata, src.read_masks(1, window=win) > 0)
    if layer.meta.get("derivative") == "slope":
        out = terrain.slope_degrees(z, *src.res)
    else:
        out = terrain.tri_riley(z)
    val = out[row - r0, col - c0]
    if not np.isfinite(val):
        return {**base, "in_coverage": False, "value": None, "status": "no_data"}
    cx, cy = src.xy(row, col)
    return {**base, "in_coverage": True, "value": float(np.float32(val)), "status": "ok",
            "pixel": {"row": int(row), "col": int(col), "centre_x": cx, "centre_y": cy}}


def inspect(catalog: Catalog, x: float, y: float) -> dict[str, Any]:
    samples = {l.id: sample_layer(catalog, l, x, y) for l in catalog.layers()}

    def first_valid(ids: list[str]) -> dict | None:
        for i in ids:
            s = samples.get(i)
            if s and s["in_coverage"]:
                return s
        return None

    # Elevation: finest available DEM at this point; all sources are listed too.
    elev = first_valid(["hirise_dtm_1", "hirise_dtm_2", "ctx_dem"])
    elev_src = {"hirise_dtm_1": "slope_hirise_1", "hirise_dtm_2": "slope_hirise_2", "ctx_dem": "slope_ctx"}
    slope = samples.get(elev_src[elev["layer"]]) if elev else first_valid(["slope_ctx"])
    if slope is not None and not slope["in_coverage"]:
        slope = first_valid(["slope_ctx"])
    summary = {
        "elevation": elev or samples.get("ctx_dem"),
        "slope": slope or samples.get("slope_ctx"),
        "thermal_inertia": samples.get("themis_ti"),
        "roughness": samples.get("tri_ctx"),
    }
    return {"summary": summary, "layers": samples}
