# 09 — Performance

## Design measures

| Concern | Measure |
|---|---|
| Large rasters | COGs with internal overviews; the browser only ever receives 256 px tiles |
| Tile cost | GDAL reads only the overlapping blocks of the right overview; empty tiles short-circuit to a cached transparent PNG |
| Caching | `Cache-Control: public, max-age=86400` + `ETag`/304; versioned tile URLs; Cloudflare edge cache |
| Independent layers | one OpenLayers tile source per layer; hidden layers make no requests |
| Derivatives | precomputed once by the pipeline, never on request |
| Point inspection | 1×1 native-resolution window reads per layer |
| Routing | corridor window, native-resolution read, vectorised cost grid, A\* in a worker thread |
| Database | SQLite (WAL) with an index on `(workspace_id, created_at)` |

## Measured in development (synthetic data, this repository's test machine)

| Operation | Size | Time |
|---|---|---|
| Cost-grid build (slope, TRI, 8 edge arrays) | 535 × 560 (whole delta, 20 m) | 0.07 s |
| A\* corner to corner | 535 × 560 | 0.53 s (242 k expansions) |
| Cost-grid build | 1200 × 1200 | 0.35 s |
| A\* corner to corner | 1200 × 1200 | 4.2 s (1.3 M expansions) |

## Production measurement

After deployment run:

```bash
python backend/scripts/benchmark.py --api https://api.astro-mars.wiki --waypoints
```

and paste its table here. It measures initial metadata load, uncached vs cacheable tile response per
layer, point inspection, routes of ~1/4/10 km, the NASA raw-image proxy and waypoint create/list/delete. Measure initial map load
and layer switching in the browser with DevTools → Performance (record: page load until the first
`ctx_ortho` tiles paint; toggling a layer until its tiles paint) and add the numbers.

| Operation | n | median | p95 | max |
|---|---:|---:|---:|---:|
| *(to be filled from the production run)* | | | | |

Targets for acceptance: initial map visible < 2.5 s on broadband; cached tile < 100 ms; uncached tile
< 400 ms; inspection < 300 ms; 20 m route across the delta < 2 s; waypoint operations < 150 ms.
