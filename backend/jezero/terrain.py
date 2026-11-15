"""Terrain derivatives computed from authentic elevation data.

All functions take a 2-D elevation array in metres with NaN marking NoData,
and pixel sizes in metres (horizontal and vertical units must agree — the
project CRS is metric, so this holds after reprojection; ``z_factor`` is
available but defaults to 1).

NoData policy: a derivative is NaN wherever any cell of its 3×3 window is
NaN, including the outermost row/column of the array. Values are never
extrapolated across gaps or edges. Large rasters are processed by
``pipeline/05_derivatives.py`` in blocks with a 1-pixel halo, which gives
results identical to processing the whole array at once.

References
  Horn, B.K.P. (1981) Hill shading and the reflectance map. Proc. IEEE 69(1).
  Riley, S.J., DeGloria, S.D., Elliot, R. (1999) A terrain ruggedness index
    that quantifies topographic heterogeneity. Intermountain J. Sci. 5.
"""
from __future__ import annotations

import numpy as np


def _windows(dem: np.ndarray) -> dict[str, np.ndarray]:
    """Return the nine shifted views a..i of a NaN-padded array.

        a b c
        d e f      row index increases southward (raster order)
        g h i
    """
    z = np.asarray(dem, dtype="f8")
    if z.ndim != 2:
        raise ValueError("DEM must be 2-D")
    p = np.pad(z, 1, mode="constant", constant_values=np.nan)
    h, w = z.shape
    return {
        "a": p[0:h, 0:w], "b": p[0:h, 1:w + 1], "c": p[0:h, 2:w + 2],
        "d": p[1:h + 1, 0:w], "e": p[1:h + 1, 1:w + 1], "f": p[1:h + 1, 2:w + 2],
        "g": p[2:h + 2, 0:w], "h": p[2:h + 2, 1:w + 1], "i": p[2:h + 2, 2:w + 2],
    }


def horn_gradients(dem: np.ndarray, res_x: float, res_y: float, z_factor: float = 1.0) -> tuple[np.ndarray, np.ndarray]:
    """Horn (1981) 3×3 finite-difference gradients.

    Returns (dz/dEast, dz/dNorth), dimensionless (m/m). ``res_y`` is the
    positive pixel height in metres.
    """
    if res_x <= 0 or res_y <= 0:
        raise ValueError("Pixel sizes must be positive metres")
    k = _windows(dem)
    dz_de = ((k["c"] + 2 * k["f"] + k["i"]) - (k["a"] + 2 * k["d"] + k["g"])) / (8.0 * res_x)
    dz_ds = ((k["g"] + 2 * k["h"] + k["i"]) - (k["a"] + 2 * k["b"] + k["c"])) / (8.0 * res_y)
    # Horn's kernel does not use the centre cell; a NoData centre must still
    # produce NoData rather than a value interpolated from its neighbours.
    centre_nan = np.isnan(k["e"])
    dz_de[centre_nan] = np.nan
    dz_ds[centre_nan] = np.nan
    return dz_de * z_factor, -dz_ds * z_factor


def slope_degrees(dem: np.ndarray, res_x: float, res_y: float, z_factor: float = 1.0) -> np.ndarray:
    """Slope magnitude in degrees (0 = flat). NaN where undefined."""
    gx, gy = horn_gradients(dem, res_x, res_y, z_factor)
    return np.degrees(np.arctan(np.hypot(gx, gy)))


def aspect_degrees(dem: np.ndarray, res_x: float, res_y: float) -> np.ndarray:
    """Downslope direction, degrees clockwise from north. NaN on flat cells."""
    gx, gy = horn_gradients(dem, res_x, res_y)
    asp = (np.degrees(np.arctan2(-gx, -gy)) + 360.0) % 360.0
    asp[(gx == 0) & (gy == 0)] = np.nan
    return asp


def hillshade(dem: np.ndarray, res_x: float, res_y: float, azimuth_deg: float = 315.0,
              altitude_deg: float = 45.0, z_factor: float = 1.0) -> np.ndarray:
    """Lambertian hillshade in [0, 1] using Horn gradients.

    Illumination azimuth is measured clockwise from north (315° = from the
    north-west), altitude above the horizon. Output = max(0, n·L) where n is
    the unit surface normal and L the unit vector toward the light source.
    NaN where the gradient is undefined.
    """
    gx, gy = horn_gradients(dem, res_x, res_y, z_factor)
    az, alt = np.radians(azimuth_deg), np.radians(altitude_deg)
    lx, ly, lz = np.sin(az) * np.cos(alt), np.cos(az) * np.cos(alt), np.sin(alt)
    norm = np.sqrt(gx * gx + gy * gy + 1.0)
    shade = (-gx * lx - gy * ly + lz) / norm
    return np.clip(shade, 0.0, 1.0)


def tri_riley(dem: np.ndarray) -> np.ndarray:
    """Terrain Ruggedness Index (Riley et al. 1999), metres.

    sqrt( Σ (z_i − z_centre)² ) over the 8 neighbours.
    """
    k = _windows(dem)
    e = k["e"]
    acc = np.zeros_like(e)
    for key in "abcdfghi":
        acc += (k[key] - e) ** 2
    return np.sqrt(acc)


def blockwise(func, dem: np.ndarray, block: int = 1024, halo: int = 1, **kwargs) -> np.ndarray:
    """Apply a 3×3-neighbourhood derivative block by block with a halo.

    Mirrors how the pipeline processes rasters too large for memory; the
    test-suite asserts the result is identical to a whole-array call.
    """
    h, w = dem.shape
    out = np.full((h, w), np.nan)
    for r0 in range(0, h, block):
        for c0 in range(0, w, block):
            r1, c1 = min(r0 + block, h), min(c0 + block, w)
            rr0, cc0 = max(r0 - halo, 0), max(c0 - halo, 0)
            rr1, cc1 = min(r1 + halo, h), min(c1 + halo, w)
            sub = func(dem[rr0:rr1, cc0:cc1], **kwargs)
            out[r0:r1, c0:c1] = sub[r0 - rr0:r0 - rr0 + (r1 - r0), c0 - cc0:c0 - cc0 + (c1 - c0)]
    return out


def to_float_with_nan(arr: np.ndarray, nodata: float | None, valid_mask: np.ndarray | None = None) -> np.ndarray:
    """Convert a raster block to float64 with NaN for NoData.

    ``valid_mask`` (True = valid) — e.g. from a GDAL mask band — takes
    precedence; ``nodata`` is applied in addition when given.
    """
    out = np.asarray(arr, dtype="f8").copy()
    if nodata is not None and np.isfinite(nodata):
        out[out == nodata] = np.nan
    if valid_mask is not None:
        out[~np.asarray(valid_mask, dtype=bool)] = np.nan
    out[~np.isfinite(out)] = np.nan
    return out
