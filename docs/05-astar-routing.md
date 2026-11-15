# 05 — Terrain-aware A\* routing

Code: `backend/jezero/routing/` — `cost.py` (cost model), `astar.py` (search), `reference.py`
(independent Dijkstra), `stats.py` (route statistics), `service.py` (raster windows, terrain source,
API glue). Tests: `backend/tests/test_routing.py`. Report: [results/astar-validation.md](results/astar-validation.md).

Every result is labelled **"Terrain-cost path estimate (not a certified safe route)"**.

## Cost function

For a move from cell *a* to its 8-neighbour *b*:

```
C(a,b) = d · [ 1 + α·½(f(s_a)+f(s_b)) + β·½(g(r_a)+g(r_b)) + γ↑·max(G,0) + γ↓·max(−G,0) ]

d   = horizontal ground distance: res (cardinal) or res·√2 (diagonal)
G   = (z_b − z_a) / d                signed grade, uphill positive
s   = Horn slope of the cell (°)      f(s) = (tan s / tan s_max)^p      ∈ [0,1]
r   = Riley TRI of the cell (m)       g(r) = r / r_ref
```

- **Slope penalty** grows smoothly and reaches α at the profile's slope limit.
- **Direction-dependent** grade terms make uphill and downhill costs differ (γ↑ ≠ γ↓).
- **Blocked cells**: NoData elevation or slope, slope > s_max, or TRI > r_max (if set).
- **Blocked moves**: either end blocked; |edge grade| > edge limit; diagonal moves whose two orthogonal
  neighbours are not both passable (**no corner cutting**).

### Profiles (`config/project.yaml → routing.profiles`)

| Profile | s_max | α | p | β (r_ref 2 m) | γ↑ | γ↓ |
|---|---:|---:|---:|---:|---:|---:|
| Cautious | 15° | 6 | 2 | 1.0 | 4 | 1 |
| Balanced (default) | 20° | 3 | 2 | 0.5 | 2 | 0.5 |
| Direct | 25° | 1 | 2 | 0 | 1 | 0 |

These are **planning weights chosen for exploration studies**, not rover mobility limits. They were
chosen so that (a) a slope at the limit costs 2–7× flat ground, (b) the profiles visibly differ in the
detours they take on synthetic and real terrain. Tune them on the real DEM with the validation script and
record the rationale here before relying on them.

## Search

- 8-connected grid, true step lengths.
- Heuristic: octile distance × res × 1.0. Every multiplier term is ≥ 0, so C(a,b) ≥ d(a,b) ≥ the octile
  step; the heuristic is **admissible and consistent**, hence A\* returns the optimal path for the model.
- Runs server-side in a worker thread. Typical times measured here (pure Python): 535×560 grid (whole
  delta at 20 m) ≈ 0.5 s worst-case corner-to-corner; 1200×1200 ≈ 4 s.

## Resolution and coverage

| Source | Effective resolution | Where usable |
|---|---|---|
| `ctx` | 20 m | whole project area — regional baseline |
| `hirise_1`, `hirise_2` | native processed (~1 m) | only inside that DTM's valid footprint |
| `auto` | HiRISE if both endpoints lie inside one HiRISE footprint and the corridor fits the cell budget, else CTX | — |

- DEM windows are read at native resolution (no overviews) with a 1-px halo; slope/TRI are recomputed
  in the window with the same code as the published rasters.
- Search first uses a corridor (endpoint bbox + max(1.5 km, ½ distance)); if no route exists inside it,
  the whole raster is searched. Cell budget 1.5 M (configurable); over budget → explicit error.
- NoData is impassable. Outside a HiRISE footprint the route **cannot** cross; the API returns 409 with an
  explanation rather than bridging the gap.
- Endpoints outside the boundary → 422; on NoData/blocked terrain → 422; no route → 409.

## Route statistics

Distance (horizontal and surface), cumulative ascent and descent, distance-weighted mean Horn slope,
maximum Horn slope on the path, steepest single step grade, start/end elevation, model cost, terrain
source and effective resolution, profile parameters, cells expanded, limitations text.

## Validation

| Requirement (brief §7.6) | Test |
|---|---|
| A\* optimal for the cost function | `test_astar_matches_dijkstra` — 4 profiles × 6 terrains × 8 pairs; plus 240 cases in the report |
| Steep terrain → detour | `test_steep_ridge_forces_detour_through_gap`, `test_steep_passable_hill_is_avoided_when_alternative_exists` |
| NoData handled | `test_nodata_barrier_without_gap_returns_explicit_error`, `test_nodata_is_never_traversed_and_buffers_cells` |
| Blocked cells never traversed | `path_is_valid` check on every route; `test_blocked_profile_slope_limit` |
| No corner cutting | `test_no_diagonal_corner_cutting` |
| Start/destination handling | `test_endpoints` |
| Stays in boundary | `test_boundary_mask_is_respected`; API rejects out-of-boundary endpoints (`test_api_smoke.py`) |
| Uphill ≠ downhill | `test_directional_costs_and_symmetry_break` |
| Statistics correct | `test_route_stats_simple_ramp` |
