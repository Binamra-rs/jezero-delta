"""Dynamic tile rendering from COGs in the project CRS.

Each tile is produced by GDAL warping (WarpedVRT) the COG onto the exact
256×256 tile grid; GDAL picks the appropriate overview, so only the needed
bytes are read. All COGs are already in the project CRS, so this is a pure
resampling step (no reprojection at request time).

Display resampling: bilinear for continuous layers and imagery (brief §4.2).
These pixels are for visualisation only — numerical values always come from
the point sampler, which reads native pixels.
"""
from __future__ import annotations

import io
from functools import lru_cache

import numpy as np
from affine import Affine
from PIL import Image
from rasterio.enums import ColorInterp, Resampling
from rasterio.vrt import WarpedVRT

from . import colormap
from .catalog import Catalog, Layer
from ..tilegrid import TileGrid

STYLE_RAMP = {"gray": "gray", "elevation": "elevation", "thermal": "thermal",
              "slope": "slope", "roughness": "roughness"}


@lru_cache(maxsize=1)
def empty_png(size: int = 256) -> bytes:
    buf = io.BytesIO()
    Image.new("RGBA", (size, size), (0, 0, 0, 0)).save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _intersects(a, b) -> bool:
    return a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]


def read_tile(catalog: Catalog, layer: Layer, bounds, size: int) -> tuple[np.ndarray, np.ndarray]:
    src = catalog.open(layer.id)
    minx, miny, maxx, maxy = bounds
    res = (maxx - minx) / size
    transform = Affine(res, 0, minx, 0, -res, maxy)
    nodata = src.nodata
    kwargs = dict(crs=src.crs, transform=transform, width=size, height=size,
                  resampling=Resampling.bilinear if layer.style != "categorical" else Resampling.nearest)
    has_alpha = ColorInterp.alpha in src.colorinterp

    if nodata is not None:
        kwargs.update(nodata=nodata, src_nodata=nodata)
    elif not has_alpha:
        kwargs.update(add_alpha=True)
    with WarpedVRT(src, **kwargs) as vrt:
        data = vrt.read(1).astype("f8")
        valid = vrt.dataset_mask() > 0
    if nodata is not None:
        valid &= data != nodata
    valid &= np.isfinite(data)
    return data, valid


def render_rgba(catalog: Catalog, grid: TileGrid, layer: Layer, z: int, x: int, y: int) -> np.ndarray | None:
    """RGBA array for one tile, or None when the tile holds no valid pixel."""
    bounds = grid.tile_bounds(z, x, y)
    if not _intersects(bounds, layer.bounds):
        return None
    data, valid = read_tile(catalog, layer, bounds, grid.tile_size)
    if not valid.any():
        return None
    if layer.style == "gray":
        vmin, vmax = layer.range or (float(np.nanmin(data[valid])), float(np.nanmax(data[valid])))
    else:
        if not layer.range:
            raise ValueError(f"Layer {layer.id} has no display range in the catalog")
        vmin, vmax = layer.range
    return colormap.apply(data, valid, vmin, vmax, STYLE_RAMP.get(layer.style, "gray"))


def render(catalog: Catalog, grid: TileGrid, layer: Layer, z: int, x: int, y: int) -> bytes:
    rgba = render_rgba(catalog, grid, layer, z, x, y)
    if rgba is None:
        return empty_png(grid.tile_size)
    buf = io.BytesIO()
    Image.fromarray(rgba, mode="RGBA").save(buf, format="PNG", compress_level=6)
    return buf.getvalue()
