# 04 — Terrain derivatives

Derived products are **calculated**, not measured. They are labelled `DERIVED` throughout the UI and
carry `JEZERO_NOTE=Derived product - not a direct measurement` in their metadata.

Implementation: `backend/jezero/terrain.py` (tested in `backend/tests/test_terrain.py`).
Production: `pipeline/04_derivatives.py`, computed once per DEM and stored as COGs.

| | Slope | Hillshade | Roughness (TRI) |
|---|---|---|---|
| Inputs | each processed DEM (`ctx_dem` 20 m, `hirise_dtm_1/2` ~1 m) | same | same |
| Output resolution | identical to input DEM | identical | identical |
| Algorithm | Horn (1981) 3×3 gradient; slope = atan(√(∂z/∂E² + ∂z/∂N²)) | Lambertian n·L with Horn gradients | Riley et al. (1999): √Σ(zᵢ − z₀)² over 8 neighbours |
| Parameters | z-factor 1 | azimuth 315°, altitude 45°, z-factor 1 | — |
| Units | degrees | 1–255 relative brightness (0 = NoData) | metres |
| Output type | Float32 | Byte | Float32 |
| Files | `slope_ctx.tif`, `slope_hirise_1.tif`, `slope_hirise_2.tif` | `hillshade_*.tif` (alignment QA only, not served as a map layer) | `tri_*.tif` |

**Units consistency.** All DEMs are in the metric project CRS, which is true-scale to < 0.1 % on the delta
and within 0.32 % anywhere inside the crater-wide boundary, so horizontal pixel size (m) and elevation (m) agree; z-factor stays 1.

**NoData.** A value is produced only where the entire 3×3 window is valid; the centre cell must also be
valid (Horn's kernel does not use it — the tests caught and fixed this). Edges of each DEM's footprint
are therefore NoData, never extrapolated.

**Block processing.** Large rasters are processed in 2048-px blocks with a 1-px halo; the test suite
asserts bit-identical NaN masks and values versus whole-array processing.

## Validation

| Check | Where | Result |
|---|---|---|
| Plane z = aE + bN → slope = atan(√(a²+b²)) exactly | `test_slope_of_plane_is_exact` | pass |
| Anisotropic pixel sizes handled | `test_anisotropic_pixels` | pass |
| Aspect points downslope (E, S) | `test_aspect_points_downslope` | pass |
| Hillshade: flat = sin(alt); facing light = 1; facing away darker | `test_hillshade_orientation` | pass |
| TRI of plane = √6·a·res | `test_tri_riley_plane` | pass |
| NoData only spreads to its 3×3 neighbourhood | `test_nodata_propagates_to_3x3_only` | pass |
| Block-wise = whole-array | `test_blockwise_identical_to_whole_array` | pass |
| Agreement with GDAL `gdaldem slope -alg Horn` on the real DEMs | step 04 report | to run on real data (threshold 0.001°) |
