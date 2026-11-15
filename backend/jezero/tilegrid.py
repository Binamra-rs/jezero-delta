"""Tile matrix set for the project CRS.

A simple, explicit pyramid: origin at the top-left corner of the project
boundary, square pixels, resolution halving at every zoom level. The same
numbers are served to the frontend (``GET /api/v1/tilegrid``) and passed
verbatim to an OpenLayers ``TileGrid``, so the client and server can never
disagree about where a tile is.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from .crs import Boundary


class TileIndexError(ValueError):
    pass


@dataclass(frozen=True)
class TileGrid:
    boundary: Boundary
    tile_size: int
    resolutions: tuple[float, ...]

    @classmethod
    def build(cls, boundary: Boundary, tile_size: int = 256, finest_resolution: float = 0.5) -> "TileGrid":
        if tile_size <= 0 or finest_resolution <= 0:
            raise ValueError("tile_size and finest_resolution must be positive")
        r0 = max(boundary.width, boundary.height) / tile_size
        n = max(1, int(math.ceil(math.log2(r0 / finest_resolution))) + 1)
        return cls(boundary, tile_size, tuple(r0 / (2 ** z) for z in range(n)))

    @property
    def origin(self) -> tuple[float, float]:
        return (self.boundary.minx, self.boundary.maxy)

    @property
    def max_zoom(self) -> int:
        return len(self.resolutions) - 1

    def matrix_size(self, z: int) -> tuple[int, int]:
        """Number of (columns, rows) of tiles needed to cover the boundary at z."""
        self._check_z(z)
        span = self.tile_size * self.resolutions[z]
        cols = max(1, math.ceil(self.boundary.width / span - 1e-9))
        rows = max(1, math.ceil(self.boundary.height / span - 1e-9))
        return cols, rows

    def tile_bounds(self, z: int, x: int, y: int) -> tuple[float, float, float, float]:
        """(minx, miny, maxx, maxy) of tile column x, row y (row 0 at the top)."""
        cols, rows = self.matrix_size(z)
        if not (0 <= x < cols and 0 <= y < rows):
            raise TileIndexError(f"Tile {z}/{x}/{y} outside the project tile matrix")
        span = self.tile_size * self.resolutions[z]
        ox, oy = self.origin
        minx = ox + x * span
        maxy = oy - y * span
        return (minx, maxy - span, minx + span, maxy)

    def zoom_for_resolution(self, res: float) -> int:
        """Smallest zoom whose resolution is <= res (i.e. at least as fine)."""
        for z, r in enumerate(self.resolutions):
            if r <= res * (1 + 1e-9):
                return z
        return self.max_zoom

    def _check_z(self, z: int) -> None:
        if not 0 <= z <= self.max_zoom:
            raise TileIndexError(f"Zoom {z} outside 0..{self.max_zoom}")

    def describe(self) -> dict:
        return {
            "origin": list(self.origin),
            "extent": list(self.boundary.bounds),
            "tile_size": self.tile_size,
            "resolutions": list(self.resolutions),
            "matrix_sizes": [list(self.matrix_size(z)) for z in range(len(self.resolutions))],
        }
