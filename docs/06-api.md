# 06 — API reference

Base: `https://api.astro-mars.wiki`. Interactive OpenAPI docs: `/api/docs`.
Coordinates are accepted as **either** `{x, y}` (project CRS metres) **or** `{lon_e, lat}`
(east-positive longitude, planetocentric latitude, degrees). Responses always return both.

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/healthz` | – | liveness |
| GET | `/readyz` | – | database + raster readiness (503 if not ready) |
| GET | `/api/v1/config` | – | CRS, boundary, tile grid, layer catalogue + legends, routing profiles |
| GET | `/api/v1/layers/{id}/coverage` | – | valid-data footprint (GeoJSON in project CRS) |
| GET | `/api/v1/tiles/{id}/{z}/{x}/{y}.png` | – | PNG tile; `Cache-Control` + `ETag`; 404 outside matrix |
| GET | `/api/v1/inspect?x=&y=` or `?lon_e=&lat=` | – | native pixel values of every layer at the point |
| GET | `/api/v1/convert?…` | – | projected ↔ geographic conversion |
| POST | `/api/v1/route` | – (rate limited) | terrain-aware A\* route estimate |
| GET / POST | `/api/v1/waypoints` | `X-Workspace-Key` | list / create in that workspace (writes rate limited) |
| GET / PATCH / DELETE | `/api/v1/waypoints/{id}` | `X-Workspace-Key` | read / edit / delete a waypoint of that workspace |
| GET | `/api/v1/raw-images` | – | NASA Mars 2020 raw images: `page, per_page (≤50), sol_min, sol_max, camera, order` |
| GET | `/api/v1/raw-images/cameras` | – | camera groups usable in `camera` |

## Examples

```http
POST /api/v1/route
{"start": {"lon_e": 77.40, "lat": 18.47}, "end": {"lon_e": 77.45, "lat": 18.445},
 "profile": "balanced", "terrain_source": "auto"}
```

Response (abridged):

```json
{"label": "Terrain-cost path estimate (not a certified safe route)",
 "geometry": {"type": "LineString", "coordinates": [[x, y], ...], "crs": "JEZERO_DELTA_EQC@v1"},
 "stats": {"distance_m": 6120.0, "ascent_m": 41.2, "descent_m": 88.9, "mean_slope_deg": 3.1,
           "max_slope_deg": 14.8, ...},
 "terrain": {"source": "ctx", "title": "CTX Elevation", "resolution_m": 20.0, "auto_selected": true},
 "profile": {...}, "limitations": "..."}
```

`GET /api/v1/inspect` returns `summary.{elevation, slope, thermal_inertia, roughness}` and `layers.{id}`; each
sample has `value`, `unit`, `source_dataset`, `resolution_m`, `in_coverage`, `status`
(`ok | no_data | outside_extent`) and `sampling` (nearest native pixel, no interpolation).

## Errors

| Status | Meaning |
|---|---|
| 400 | missing or malformed `X-Workspace-Key` |
| 502 | NASA raw-image feed unreachable or returned an unexpected shape |
| 404 | unknown layer, tile outside matrix, waypoint not found **or not yours** (no existence leak) |
| 409 | no traversable route under the chosen profile; duplicate account |
| 422 | invalid input: malformed or non-finite coordinates, outside the project boundary, endpoint on NoData, unknown profile, corridor too large |
| 429 | rate limited (`Retry-After` header) |

## Security notes

- Layers are addressed by catalogue id only; file paths are resolved server-side and confined to `processed/`.
- No accounts. Waypoints are scoped by an anonymous workspace key (≥ 32 URL-safe chars, generated in the browser);
  only its SHA-256 hash is stored. Anyone holding a key can edit that workspace — treat it like a password.
- The NASA proxy only forwards https image URLs on `*.nasa.gov`, validates every parameter, and caches responses.
- CORS: explicit production origins only; the API refuses to start with a localhost origin in production.
- Every waypoint query is scoped in SQL by the workspace resolved from the key.
