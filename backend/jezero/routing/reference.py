"""Independent Dijkstra reference used to validate A* (tests and CLI only).

Builds an explicit sparse directed graph from the same EdgeWeights and runs
SciPy's compiled Dijkstra — a separate code path from astar.py.
"""
from __future__ import annotations

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra

from .cost import DIRECTIONS, EdgeWeights


def edge_graph(edges: EdgeWeights) -> csr_matrix:
    h, w = edges.shape
    rows, cols = np.mgrid[0:h, 0:w]
    src, dst, wt = [], [], []
    for k, (dr, dc) in enumerate(DIRECTIONS):
        wk = edges.weights[k]
        ok = np.isfinite(wk)
        r, c = rows[ok], cols[ok]
        src.append(r * w + c)
        dst.append((r + dr) * w + (c + dc))
        wt.append(wk[ok])
    n = h * w
    return csr_matrix((np.concatenate(wt), (np.concatenate(src), np.concatenate(dst))), shape=(n, n))


def dijkstra_cost(edges: EdgeWeights, start: tuple[int, int], goal: tuple[int, int]) -> tuple[float, list[int]]:
    h, w = edges.shape
    s, t = start[0] * w + start[1], goal[0] * w + goal[1]
    dist, pred = dijkstra(edge_graph(edges), directed=True, indices=s, return_predecessors=True)
    if not np.isfinite(dist[t]):
        return float("inf"), []
    path = [t]
    while path[-1] != s:
        path.append(int(pred[path[-1]]))
    return float(dist[t]), path[::-1]
