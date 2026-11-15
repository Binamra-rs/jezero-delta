"""Route statistics computed from the terrain grid along a path."""
from __future__ import annotations

import math
from dataclasses import dataclass, asdict

import numpy as np

from .cost import DIRECTIONS, EdgeWeights


@dataclass
class RouteStats:
    distance_m: float               # horizontal (map) length
    surface_distance_m: float       # length including elevation change
    ascent_m: float
    descent_m: float
    mean_slope_deg: float           # distance-weighted mean of local Horn slope
    max_slope_deg: float            # max local Horn slope of any path cell
    max_edge_grade_deg: float       # steepest single cell-to-cell grade
    start_elevation_m: float
    end_elevation_m: float
    cost: float
    n_cells: int

    def as_dict(self) -> dict:
        return asdict(self)


def route_stats(path: list[int], elev: np.ndarray, slope: np.ndarray, edges: EdgeWeights) -> RouteStats:
    h, w = elev.shape
    z = elev.reshape(-1)
    s = slope.reshape(-1)
    dir_index = {(dr, dc): k for k, (dr, dc) in enumerate(DIRECTIONS)}
    dist = surf = asc = desc = slope_w = 0.0
    max_grade = 0.0
    cost = 0.0
    for a, b in zip(path[:-1], path[1:], strict=False):
        ra, ca = divmod(a, w)
        rb, cb = divmod(b, w)
        dr, dc = rb - ra, cb - ca
        d = edges.res * math.hypot(dr, dc)
        dz = float(z[b] - z[a])
        dist += d
        surf += math.hypot(d, dz)
        if dz > 0:
            asc += dz
        else:
            desc -= dz
        slope_w += d * 0.5 * (float(s[a]) + float(s[b]))
        max_grade = max(max_grade, math.degrees(math.atan(abs(dz) / d)))
        cost += float(edges.weights[dir_index[(dr, dc)], ra, ca])
    idx = np.asarray(path)
    return RouteStats(
        distance_m=dist,
        surface_distance_m=surf,
        ascent_m=asc,
        descent_m=desc,
        mean_slope_deg=(slope_w / dist) if dist > 0 else float(s[path[0]]),
        max_slope_deg=float(np.max(s[idx])),
        max_edge_grade_deg=max_grade,
        start_elevation_m=float(z[path[0]]),
        end_elevation_m=float(z[path[-1]]),
        cost=cost,
        n_cells=len(path),
    )
