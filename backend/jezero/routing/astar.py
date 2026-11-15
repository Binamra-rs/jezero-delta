"""A* search on an 8-connected terrain-cost grid.

The heuristic is the octile distance between cells multiplied by the profile's
minimum cost multiplier (1.0). Because every edge cost is ≥ its horizontal
length (see cost.py), the heuristic never overestimates and is consistent,
so the first time the goal is popped its cost is optimal for the configured
cost function. Validated against an independent Dijkstra implementation in
tests/test_routing.py.
"""
from __future__ import annotations

import heapq
import math
from array import array
from dataclasses import dataclass

import numpy as np

from .cost import DIRECTIONS, EdgeWeights

SQRT2_M1 = math.sqrt(2.0) - 1.0


class NoRouteError(RuntimeError):
    """No route exists under the configured mobility profile."""


class BlockedEndpointError(ValueError):
    """Start or goal lies on NoData or blocked terrain."""


@dataclass
class SearchResult:
    path: list[int]          # flat cell indices, start → goal
    cost: float
    expansions: int


def octile(r0: int, c0: int, r1: int, c1: int, res: float) -> float:
    dr, dc = abs(r1 - r0), abs(c1 - c0)
    return res * (max(dr, dc) + SQRT2_M1 * min(dr, dc))


def astar(edges: EdgeWeights, start: tuple[int, int], goal: tuple[int, int],
          heuristic_weight: float = 1.0, max_expansions: int | None = None) -> SearchResult:
    """Return the minimum-cost path from start to goal (row, col) cells.

    ``heuristic_weight`` must be ≤ the minimum cost multiplier (1.0) to keep
    optimality; 0 turns A* into Dijkstra.
    """
    h_rows, w_cols = edges.shape
    n = h_rows * w_cols
    for name, (r, c) in (("start", start), ("goal", goal)):
        if not (0 <= r < h_rows and 0 <= c < w_cols):
            raise BlockedEndpointError(f"{name} cell is outside the terrain grid")
        if not edges.passable[r, c]:
            raise BlockedEndpointError(f"{name} lies on NoData or terrain blocked by the profile")
    if heuristic_weight < 0 or heuristic_weight > 1.0:
        raise ValueError("heuristic_weight must be in [0, 1] to remain admissible")

    s = start[0] * w_cols + start[1]
    t = goal[0] * w_cols + goal[1]
    if s == t:
        return SearchResult([s], 0.0, 0)

    res = edges.res * heuristic_weight
    gr, gc = goal
    w_views = [memoryview(np.ascontiguousarray(edges.weights[k]).reshape(-1)) for k in range(8)]
    offsets = [dr * w_cols + dc for dr, dc in DIRECTIONS]
    inf = math.inf

    g = array("d", [inf]) * n
    parent = array("q", [-1]) * n
    closed = bytearray(n)
    g[s] = 0.0
    heap: list[tuple[float, float, int]] = []
    h0 = octile(start[0], start[1], gr, gc, res)
    heapq.heappush(heap, (h0, h0, s))
    expansions = 0
    push, pop = heapq.heappush, heapq.heappop

    while heap:
        _, _, u = pop(heap)
        if closed[u]:
            continue
        if u == t:
            break
        closed[u] = 1
        expansions += 1
        if max_expansions is not None and expansions > max_expansions:
            raise NoRouteError("Search exceeded the expansion budget")
        gu = g[u]
        for k in range(8):
            w = w_views[k][u]
            if w == inf:
                continue
            v = u + offsets[k]
            if closed[v]:
                continue
            nv = gu + w
            if nv < g[v]:
                g[v] = nv
                parent[v] = u
                vr, vc = divmod(v, w_cols)
                dr, dc = abs(gr - vr), abs(gc - vc)
                hv = res * (dr + dc + (SQRT2_M1 - 1.0) * (dr if dr < dc else dc))
                push(heap, (nv + hv, hv, v))
    else:
        raise NoRouteError("No traversable route connects the two points under this profile")

    if g[t] == inf:
        raise NoRouteError("No traversable route connects the two points under this profile")
    path = [t]
    while path[-1] != s:
        path.append(parent[path[-1]])
    path.reverse()
    return SearchResult(path, g[t], expansions)
