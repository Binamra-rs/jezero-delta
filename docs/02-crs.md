# 02 — Canonical Mars coordinate reference system

## Definition (`config/project.yaml → crs`, version 1)

| Parameter | Value |
|---|---|
| Body | Mars |
| Reference surface | Sphere, R = 3 396 190 m (Mars IAU 2000 sphere used by USGS Mars 2020 map products) |
| Projection | Equidistant Cylindrical (Equirectangular) |
| Central meridian | 77.40° E |
| Standard parallel (true scale) | 18.45° N |
| Latitude of origin | 0° |
| False easting / northing | 0 / 0 m |
| Linear units | metre |
| Latitude | planetocentric, north positive |
| Longitude | east positive; displayed 0–360° |

```
+proj=eqc +lat_ts=18.45 +lat_0=0 +lon_0=77.4 +x_0=0 +y_0=0 +R=3396190 +units=m +no_defs
```

### Why this CRS

- **Mars, not Earth.** No WGS84 or EPSG:3857 anywhere in the stack. OpenLayers uses this CRS
  through proj4js; its point-resolution function is overridden with the Mars formula so the scale
  bar is not computed on Earth's radius.
- **Matches the sources.** The USGS Jezero CTX products are equirectangular on the 3 396 190 m
  sphere, so for them reprojection is a shift/rescale of the same projection family — minimum
  resampling distortion.
- **True scale on the delta.** With the standard parallel at 18.45° N, the east–west scale error
  on the delta (18.38–18.56° N) is below 0.1 % (`tests/test_crs_tilegrid.py`). Across the
  crater-wide boundary (17.90–18.86° N) it stays within +0.32 % / −0.24 % (worst at the southern
  and northern edges). The meridian is always true scale. The CRS was deliberately left at v1 when
  the boundary grew, so stored waypoints stay valid.
- **Sphere ⇒ one latitude.** On a sphere planetocentric and planetographic latitudes are identical,
  so the displayed latitude is unambiguous.

## Conversions

Implemented in closed form (exact on a sphere):

- `x = R · cos(φ_ts) · Δλ`, `y = R · φ` (radians, Δλ wrapped to ±180°)
- inverse likewise; longitude normalised to [0, 360).

The same equations are in `backend/jezero/crs.py` and `frontend/src/lib/crs.ts`; tests on both sides
use identical reference values. `pytest` also cross-checks against PROJ when pyproj is present.

## Source → project transformations (step 02/03)

For every source file the stored CRS is parsed and classified:

| Class | Condition | Handling |
|---|---|---|
| `sphere_same` | sphere, R = 3 396 190 m | angles unchanged |
| `sphere_other` | sphere, different R (e.g. 3 389 500 m) | angles unchanged; distances recomputed on project sphere |
| `ellipsoid` + planetographic | a ≠ b, declared planetographic | explicit `+proj=geoc` step converts to planetocentric |
| `ellipsoid` + planetocentric | a ≠ b, declared planetocentric | angles unchanged |
| non-Mars / missing | a outside 3.37–3.40 × 10⁶ m, or no CRS | **pipeline stops** |

Each dataset gets an explicit PROJ pipeline (written to `crs_validation.json`) that is passed to
`gdalwarp -ct`, so GDAL can never substitute an implicit "ballpark" datum transformation. For an
ellipsoidal source the latitude type must be declared in the config after reading the product label;
the pipeline refuses to guess. At Jezero's latitude a wrong guess would misplace data by roughly
0.2° (~12 km), which is why this is a hard stop.

## Validation

- `07-alignment.md`: sub-pixel FFT cross-correlation of HiRISE vs CTX hillshade (same illumination),
  in metres; flags any median offset > 10 m. Optional landmark table (`config/landmarks.yaml`).
- `06-vertical.md`: HiRISE − CTX elevation statistics (mean, median, NMAD, RMSE, plane tilt).
- **No dataset is ever shifted, scaled or re-labelled to make it line up.** A flagged offset is
  investigated first. If a correction is justified, it is recorded below with evidence, applied only to
  a derived product, and the CRS version is bumped if CRS parameters change.

### Correction log

| Date | Dataset | Correction | Evidence | Approved by |
|---|---|---|---|---|
| — | — | none | — | — |

## Changing the CRS

1. Edit `config/project.yaml`, increment `crs.version`.
2. Re-run the pipeline. The API refuses to start if `catalog.json` was built for another CRS version.
3. Existing waypoints keep their `crs_version`; re-project them with a one-off script if needed.
