"""Canonical Mars coordinate reference system for the Jezero Delta project.

The project CRS is an equidistant cylindrical (equirectangular) projection on
the Mars IAU 2000 sphere (R = 3 396 190 m). On a sphere the forward and inverse
equations are closed-form and exact, so they are implemented here directly:
this module has no dependency on PROJ and is used both by the API and by the
tests. ``tests/test_crs.py`` cross-checks it against pyproj when pyproj is
installed, and the frontend uses the identical proj4 string via proj4js.

Conventions (see docs/02-crs.md):
  * latitude  : planetocentric degrees, north positive, [-90, 90]
  * longitude : east-positive degrees, displayed in [0, 360)
  * x, y      : metres in the projected CRS
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping

import numpy as np


class CoordinateError(ValueError):
    """Raised for malformed or out-of-domain coordinates."""


def normalize_lon_360(lon: float) -> float:
    """Return longitude in the east-positive [0, 360) domain."""
    out = math.fmod(lon, 360.0)
    if out < 0:
        out += 360.0
    # guard -0.0 and 360.0 produced by floating point
    return 0.0 if out == 360.0 else out + 0.0


def _wrap_delta(dlon: float) -> float:
    """Wrap a longitude difference into [-180, 180)."""
    return ((dlon + 180.0) % 360.0) - 180.0


@dataclass(frozen=True)
class MarsEquirectangular:
    radius_m: float
    lon0_deg: float
    lat_ts_deg: float
    lat0_deg: float = 0.0
    false_easting: float = 0.0
    false_northing: float = 0.0
    crs_id: str = "JEZERO_DELTA_EQC"
    version: int = 1

    # ------------------------------------------------------------------ build
    @classmethod
    def from_config(cls, cfg: Mapping[str, Any]) -> "MarsEquirectangular":
        if str(cfg.get("body", "")).lower() != "mars":
            raise ValueError("Project CRS must be defined on Mars")
        if cfg.get("projection") != "equirectangular":
            raise ValueError("Only the equirectangular project CRS is implemented")
        r = float(cfg["radius_m"])
        if not 3.37e6 < r < 3.40e6:
            raise ValueError(f"Radius {r} m is not a Mars reference radius")
        return cls(
            radius_m=r,
            lon0_deg=float(cfg["central_meridian_deg_e"]),
            lat_ts_deg=float(cfg["standard_parallel_deg"]),
            lat0_deg=float(cfg.get("latitude_of_origin_deg", 0.0)),
            false_easting=float(cfg.get("false_easting_m", 0.0)),
            false_northing=float(cfg.get("false_northing_m", 0.0)),
            crs_id=str(cfg.get("id", "JEZERO_DELTA_EQC")),
            version=int(cfg.get("version", 1)),
        )

    # ------------------------------------------------------------- strings
    @property
    def proj4(self) -> str:
        return (
            f"+proj=eqc +lat_ts={self.lat_ts_deg} +lat_0={self.lat0_deg} "
            f"+lon_0={self.lon0_deg} +x_0={self.false_easting} +y_0={self.false_northing} "
            f"+R={self.radius_m} +units=m +no_defs +type=crs"
        )

    @property
    def geographic_proj4(self) -> str:
        return f"+proj=longlat +R={self.radius_m} +no_defs +type=crs"

    @property
    def wkt2(self) -> str:
        r = self.radius_m
        return (
            'PROJCRS["Jezero Delta Equirectangular (Mars 2000 sphere)",'
            'BASEGEOGCRS["Mars 2000 sphere (planetocentric)",'
            f'DATUM["Mars 2000",ELLIPSOID["Mars 2000 sphere",{r},0,LENGTHUNIT["metre",1]]],'
            'PRIMEM["Reference meridian",0,ANGLEUNIT["degree",0.0174532925199433]]],'
            'CONVERSION["Equidistant Cylindrical",METHOD["Equidistant Cylindrical",ID["EPSG",1028]],'
            f'PARAMETER["Latitude of 1st standard parallel",{self.lat_ts_deg},ANGLEUNIT["degree",0.0174532925199433]],'
            f'PARAMETER["Longitude of natural origin",{self.lon0_deg},ANGLEUNIT["degree",0.0174532925199433]],'
            f'PARAMETER["False easting",{self.false_easting},LENGTHUNIT["metre",1]],'
            f'PARAMETER["False northing",{self.false_northing},LENGTHUNIT["metre",1]]],'
            'CS[Cartesian,2],AXIS["easting (X)",east,ORDER[1],LENGTHUNIT["metre",1]],'
            'AXIS["northing (Y)",north,ORDER[2],LENGTHUNIT["metre",1]],'
            'REMARK["Planetocentric latitude, east-positive longitude. Jezero Delta Explorer CRS"]]'
        )

    # --------------------------------------------------------------- maths
    @property
    def _k(self) -> float:
        return self.radius_m * math.cos(math.radians(self.lat_ts_deg))

    def forward(self, lon_e: float, lat: float) -> tuple[float, float]:
        """Planetocentric lon/lat (deg, east-positive) -> projected x/y (m)."""
        if not (math.isfinite(lon_e) and math.isfinite(lat)):
            raise CoordinateError("Coordinates must be finite numbers")
        if not -90.0 <= lat <= 90.0:
            raise CoordinateError(f"Latitude {lat} outside [-90, 90]")
        dlon = _wrap_delta(lon_e - self.lon0_deg)
        x = self.false_easting + self._k * math.radians(dlon)
        y = self.false_northing + self.radius_m * math.radians(lat - self.lat0_deg)
        return x, y

    def inverse(self, x: float, y: float) -> tuple[float, float]:
        """Projected x/y (m) -> (lon_e in [0,360), planetocentric lat)."""
        if not (math.isfinite(x) and math.isfinite(y)):
            raise CoordinateError("Coordinates must be finite numbers")
        lat = self.lat0_deg + math.degrees((y - self.false_northing) / self.radius_m)
        if not -90.0 <= lat <= 90.0:
            raise CoordinateError("Projected y is outside the valid domain")
        lon = self.lon0_deg + math.degrees((x - self.false_easting) / self._k)
        return normalize_lon_360(lon), lat

    def forward_array(self, lon_e: np.ndarray, lat: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        dlon = ((np.asarray(lon_e, dtype="f8") - self.lon0_deg + 180.0) % 360.0) - 180.0
        x = self.false_easting + self._k * np.radians(dlon)
        y = self.false_northing + self.radius_m * np.radians(np.asarray(lat, dtype="f8") - self.lat0_deg)
        return x, y

    def inverse_array(self, x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        lat = self.lat0_deg + np.degrees((np.asarray(y, dtype="f8") - self.false_northing) / self.radius_m)
        lon = self.lon0_deg + np.degrees((np.asarray(x, dtype="f8") - self.false_easting) / self._k)
        return np.mod(lon, 360.0), lat

    def scale_factor_x(self, lat: float) -> float:
        """East-west point scale factor at latitude ``lat`` (1.0 on lat_ts)."""
        return math.cos(math.radians(self.lat_ts_deg)) / math.cos(math.radians(lat))

    def describe(self) -> dict[str, Any]:
        return {
            "id": self.crs_id,
            "version": self.version,
            "body": "Mars",
            "reference_surface": f"sphere R={self.radius_m:.0f} m (Mars IAU 2000)",
            "projection": "Equidistant Cylindrical (Equirectangular)",
            "central_meridian_deg_e": self.lon0_deg,
            "standard_parallel_deg": self.lat_ts_deg,
            "latitude_of_origin_deg": self.lat0_deg,
            "linear_units": "metre",
            "latitude_type": "planetocentric",
            "longitude_direction": "positive east",
            "longitude_domain": "0 to 360",
            "proj4": self.proj4,
            "geographic_proj4": self.geographic_proj4,
            "wkt2": self.wkt2,
        }


@dataclass(frozen=True)
class Boundary:
    """Axis-aligned project boundary in projected metres."""

    minx: float
    miny: float
    maxx: float
    maxy: float

    @classmethod
    def from_config(cls, cfg: Mapping[str, Any], crs: MarsEquirectangular) -> "Boundary":
        lon_min, lon_max = float(cfg["lon_min_e"]), float(cfg["lon_max_e"])
        lat_min, lat_max = float(cfg["lat_min_n"]), float(cfg["lat_max_n"])
        if not (lon_min < lon_max and lat_min < lat_max):
            raise ValueError("Boundary min must be < max")
        x0, y0 = crs.forward(lon_min, lat_min)
        x1, y1 = crs.forward(lon_max, lat_max)
        snap = float(cfg.get("snap_m", 0) or 0)
        if snap > 0:
            # expand outward to a whole multiple of the snap size
            x0 = math.floor(x0 / snap) * snap
            y0 = math.floor(y0 / snap) * snap
            x1 = math.ceil(x1 / snap) * snap
            y1 = math.ceil(y1 / snap) * snap
        return cls(x0, y0, x1, y1)

    def contains(self, x: float, y: float) -> bool:
        return self.minx <= x <= self.maxx and self.miny <= y <= self.maxy

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        return (self.minx, self.miny, self.maxx, self.maxy)

    @property
    def width(self) -> float:
        return self.maxx - self.minx

    @property
    def height(self) -> float:
        return self.maxy - self.miny
