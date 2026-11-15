"""A* validation: optimality vs Dijkstra and terrain-behaviour checks (brief §7.6)."""
import math

import numpy as np
import pytest
from scipy.ndimage import gaussian_filter

from jezero import terrain
from jezero.routing.astar import BlockedEndpointError, NoRouteError, astar, octile
from jezero.routing.cost import DIRECTIONS, CostProfile, build_edge_weights
from jezero.routing.reference import dijkstra_cost
from jezero.routing.stats import route_stats

RES = 20.0

PROFILES = {
    "cautious": CostProfile("cautious", "Cautious", "", 15, 15, alpha=6, beta=1, roughness_ref_m=2, gamma_up=4, gamma_down=1),
    "balanced": CostProfile("balanced", "Balanced", "", 20, 20, alpha=3, beta=0.5, roughness_ref_m=2, gamma_up=2, gamma_down=0.5),
    "direct": CostProfile("direct", "Direct", "", 25, 25, alpha=1),
    "distance_only": CostProfile("distance_only", "", "", 89, 89, alpha=0),
}


def synthetic_dem(seed, h=60, w=80, relief=120.0, nan_frac=0.0):
    rng = np.random.default_rng(seed)
    z = gaussian_filter(rng.normal(size=(h, w)), 4)
    z = (z - z.min()) / (np.ptp(z) + 1e-12) * relief
    if nan_frac:
        holes = gaussian_filter(rng.normal(size=(h, w)), 3)
        z[holes > np.quantile(holes, 1 - nan_frac)] = np.nan
    return z


def grids(z, profile):
    s = terrain.slope_degrees(z, RES, RES)
    r = terrain.tri_riley(z)
    return s, r, build_edge_weights(z, s, RES, profile, rough=r)


def path_is_valid(path, edges):
    h, w = edges.shape
    dmap = {d: k for k, d in enumerate(DIRECTIONS)}
    total = 0.0
    for a, b in zip(path[:-1], path[1:], strict=False):
        ra, ca = divmod(a, w); rb, cb = divmod(b, w)
        k = dmap[(rb - ra, cb - ca)]
        wgt = edges.weights[k, ra, ca]
        assert np.isfinite(wgt), "path uses a blocked edge"
        total += wgt
    assert all(edges.passable.reshape(-1)[p] for p in path), "path visits a blocked cell"
    return total


def random_passable_pair(rng, edges):
    cells = np.argwhere(edges.passable)
    a, b = cells[rng.choice(len(cells), 2, replace=False)]
    return tuple(int(v) for v in a), tuple(int(v) for v in b)


@pytest.mark.parametrize("profile", list(PROFILES))
@pytest.mark.parametrize("seed", range(6))
def test_astar_matches_dijkstra(profile, seed):
    z = synthetic_dem(seed, relief=150.0, nan_frac=0.08 if seed % 2 else 0.0)
    _, _, edges = grids(z, PROFILES[profile])
    rng = np.random.default_rng(100 + seed)
    for _ in range(8):
        s, t = random_passable_pair(rng, edges)
        ref_cost, _ = dijkstra_cost(edges, s, t)
        if math.isinf(ref_cost):
            with pytest.raises(NoRouteError):
                astar(edges, s, t)
            continue
        res = astar(edges, s, t)
        assert res.cost == pytest.approx(ref_cost, rel=1e-9, abs=1e-9)
        assert path_is_valid(res.path, edges) == pytest.approx(res.cost, rel=1e-9)
        assert res.path[0] == s[0] * edges.shape[1] + s[1]
        assert res.path[-1] == t[0] * edges.shape[1] + t[1]
        # admissibility: heuristic never exceeds the true cost
        assert octile(*s, *t, RES) <= res.cost + 1e-9


def test_flat_terrain_cost_equals_octile_distance():
    z = np.full((30, 40), 100.0)
    _, _, edges = grids(z, PROFILES["balanced"])
    res = astar(edges, (5, 5), (20, 33))
    assert res.cost == pytest.approx(octile(5, 5, 20, 33, RES))


def test_steep_ridge_forces_detour_through_gap():
    z = np.full((41, 41), 0.0)
    z[:, 18:23] = 400.0           # 400 m wall, far beyond every slope limit
    z[30:35, 18:23] = 0.0         # a gap in the wall
    _, _, edges = grids(z, PROFILES["balanced"])
    res = astar(edges, (10, 5), (10, 35))
    rows = [p // 41 for p in res.path]
    cols = [p % 41 for p in res.path]
    crossing = [r for r, c in zip(rows, cols, strict=False) if 18 <= c <= 22]
    assert crossing and all(30 <= r <= 34 for r in crossing)
    assert res.cost > octile(10, 5, 10, 35, RES)


def test_steep_passable_hill_is_avoided_when_alternative_exists():
    h, w = 41, 61
    rows, cols = np.mgrid[0:h, 0:w]
    hill = 60.0 * np.exp(-(((rows - 20) ** 2) + ((cols - 30) ** 2)) / (2 * 5.0 ** 2))
    z = hill
    s = terrain.slope_degrees(z, RES, RES)
    assert np.nanmax(s) < 20  # passable under 'balanced'
    e_dist = build_edge_weights(z, s, RES, PROFILES["distance_only"])
    e_bal = build_edge_weights(z, s, RES, PROFILES["balanced"], rough=terrain.tri_riley(z))
    start, goal = (20, 5), (20, 55)
    straight = astar(e_dist, start, goal)
    aware = astar(e_bal, start, goal)
    max_slope_straight = max(s.reshape(-1)[p] for p in straight.path)
    max_slope_aware = max(s.reshape(-1)[p] for p in aware.path)
    assert max_slope_aware < max_slope_straight
    st_aware = route_stats(aware.path, z, s, e_bal)
    st_straight = route_stats(straight.path, z, s, e_dist)
    assert st_aware.distance_m > st_straight.distance_m   # took a detour
    assert st_aware.ascent_m < st_straight.ascent_m


def test_nodata_barrier_without_gap_returns_explicit_error():
    z = np.full((30, 30), 10.0)
    z[:, 14:16] = np.nan
    _, _, edges = grids(z, PROFILES["direct"])
    with pytest.raises(NoRouteError):
        astar(edges, (10, 3), (10, 26))


def test_nodata_is_never_traversed_and_buffers_cells():
    z = np.full((30, 30), 10.0)
    z[:, 14:16] = np.nan
    z[25:28, 14:16] = 10.0  # gap
    s, _, edges = grids(z, PROFILES["direct"])
    res = astar(edges, (10, 3), (10, 26))
    flat = z.reshape(-1)
    assert all(np.isfinite(flat[p]) for p in res.path)
    # slope is NaN adjacent to NoData, so those cells are blocked too
    assert all(np.isfinite(s.reshape(-1)[p]) for p in res.path)


def test_no_diagonal_corner_cutting():
    z = np.full((6, 6), 0.0)
    z[2, 3] = np.nan
    s = terrain.slope_degrees(np.full((6, 6), 0.0), RES, RES)
    s[2, 3] = np.nan
    edges = build_edge_weights(np.where(np.isnan(s), np.nan, 0.0), s, RES, PROFILES["direct"])
    # moving NE from (3,2) to (2,3)'s neighbour would cut the corner of blocked (2,3)
    k_ne = DIRECTIONS.index((-1, 1))
    assert np.isinf(edges.weights[k_ne, 3, 2])   # target (2,3) blocked
    assert np.isinf(edges.weights[k_ne, 2, 2])   # passes between (1,2) and (2,3)
    assert np.isfinite(edges.weights[k_ne, 4, 1])


def test_directional_costs_and_symmetry_break():
    rows, cols = np.mgrid[0:20, 0:40]
    z = cols * RES * math.tan(math.radians(5))  # 5° ramp rising east
    s = terrain.slope_degrees(z, RES, RES)
    edges = build_edge_weights(z, s, RES, PROFILES["balanced"], rough=terrain.tri_riley(z))
    up = astar(edges, (10, 2), (10, 37)).cost
    down = astar(edges, (10, 37), (10, 2)).cost
    assert up > down
    assert dijkstra_cost(edges, (10, 2), (10, 37))[0] == pytest.approx(up)


def test_endpoints():
    z = synthetic_dem(9)
    z[0:5, 0:5] = np.nan
    _, _, edges = grids(z, PROFILES["direct"])
    ok = tuple(int(v) for v in np.argwhere(edges.passable)[len(np.argwhere(edges.passable)) // 2])
    with pytest.raises(BlockedEndpointError):
        astar(edges, (2, 2), ok)
    with pytest.raises(BlockedEndpointError):
        astar(edges, ok, (999, 1))
    r = astar(edges, ok, ok)
    assert r.cost == 0 and len(r.path) == 1


def test_boundary_mask_is_respected():
    z = np.full((30, 30), 0.0)
    s = terrain.slope_degrees(z, RES, RES)
    mask = np.ones_like(z, dtype=bool)
    mask[:, 20:] = False
    edges = build_edge_weights(z, s, RES, PROFILES["direct"], mask=mask)
    res = astar(edges, (10, 3), (12, 18))
    assert all(p % 30 < 20 for p in res.path)
    with pytest.raises(BlockedEndpointError):
        astar(edges, (10, 3), (10, 25))


def test_blocked_profile_slope_limit():
    rows, cols = np.mgrid[0:20, 0:40]
    z = cols * RES * math.tan(math.radians(18))
    s = terrain.slope_degrees(z, RES, RES)
    cautious = build_edge_weights(z, s, RES, PROFILES["cautious"], rough=terrain.tri_riley(z))
    balanced = build_edge_weights(z, s, RES, PROFILES["balanced"], rough=terrain.tri_riley(z))
    assert not cautious.passable[5:15, 5:35].any()   # 18° > 15° limit
    assert balanced.passable[5:15, 5:35].all()        # 18° < 20° limit


def test_route_stats_simple_ramp():
    z = np.tile(np.arange(30, dtype="f8") * 2.0, (10, 1))  # +2 m per 20 m cell eastward
    s = terrain.slope_degrees(z, RES, RES)
    edges = build_edge_weights(z, s, RES, PROFILES["distance_only"])
    res = astar(edges, (5, 2), (5, 27))
    st = route_stats(res.path, z, s, edges)
    assert st.distance_m == pytest.approx(25 * RES)
    assert st.ascent_m == pytest.approx(50.0) and st.descent_m == 0
    assert st.max_slope_deg == pytest.approx(math.degrees(math.atan(0.1)))
    assert st.cost == pytest.approx(res.cost)


def test_profile_validation():
    with pytest.raises(ValueError):
        CostProfile("x", "", "", 20, 20, alpha=-1)
