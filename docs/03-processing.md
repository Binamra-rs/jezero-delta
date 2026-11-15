# 03 — Processing and reprojection pipeline

Run everything with `pipeline/run_all.sh` (or the pipeline Docker image). Each step is idempotent,
never writes to `raw/`, and writes both a JSON (machine) and a Markdown (human) report.

| Step | Script | Does | Stops when |
|---|---|---|---|
| 01 | `01_inventory.py` | checksums, full block decode, metadata | file missing, checksum changed, unreadable blocks |
| 02 | `02_crs_validation.py` | parse CRS, Mars check, explicit PROJ pipeline, ground pixel size, delta coverage | no/non-Mars CRS, ellipsoid without declared latitude type, no intersection with boundary |
| 03 | `03_reproject.py` | gdalwarp (VRT) → gdal_translate COG in project CRS, verify CRS + grid alignment | verification fails |
| 04 | `04_derivatives.py` | slope, hillshade, TRI for each DEM, gdaldem cross-check | gdaldem slope differs by ≥ 0.001° |
| 05 | `05_coverage.py` | valid-data footprints, % of boundary, pairwise overlaps, GeoJSON outlines | a dataset has no data in the boundary |
| 06 | `06_vertical.py` | HiRISE vs CTX and HiRISE vs HiRISE elevation differences | (reports only) |
| 07 | `07_alignment.py` | horizontal offset measurement, landmarks | (reports only) |
| 08 | `08_catalog.py` | `processed/catalog.json` (the API's layer registry) | — |

## Reprojection choices (step 03)

| Dataset kind | Warp resampling | Overview resampling | Output type / NoData |
|---|---|---|---|
| Orthomosaic | bilinear (configurable `cubic`) | AVERAGE | source type; source NoData or alpha mask |
| Elevation, thermal inertia — target ≈ native | bilinear | AVERAGE | Float32; −3.4028235e38 |
| Elevation, thermal inertia — target > 1.5× native | average (area) | AVERAGE | Float32 |
| Categorical (none at present) | nearest | NEAREST | source type |

- **Target pixel size** = larger native ground-pixel dimension, measured in the project CRS, rounded
  *up* to the millimetre (or `target_resolution_m`, which may not be finer than native).
- **Grid**: every output is aligned to the boundary's top-left corner; extent = footprint ∩ boundary.
- **COG**: DEFLATE (+ predictor for float), 512 px blocks, internal overviews, `SPARSE_OK`.
- **Provenance**: DOI, product id, raw SHA-256, CRS id/version, resampling, native pixel size and date
  are embedded as metadata items in every COG.
- Exact commands for every dataset are stored in `reports/reprojection.json`.

## Tiles

COGs are served by the API's renderer (`backend/jezero/raster/tiles.py`): GDAL warps the COG onto the
exact tile (WarpedVRT), automatically using the right overview. The tile matrix is defined in the
project CRS (`backend/jezero/tilegrid.py`): origin = boundary top-left, 256 px tiles, resolution halving
per zoom down to 0.5 m. `GET /api/v1/config` returns it and the frontend builds an OpenLayers `TileGrid`
from those exact numbers.

Tile pixels are for display only. Numbers shown to users always come from the point sampler, which reads
native pixels.

## Re-running

Changing the boundary, the CRS, a dataset or a derivative parameter requires re-running from the affected
step onward, then restarting the API (it checks `catalog.json` matches the config at start-up).
