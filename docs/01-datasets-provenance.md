# 01 — Datasets and provenance

The five datasets below are the application's **only** authoritative sources. Everything else
(slope, hillshade, TRI, coverage outlines, statistics) is derived and labelled as such.

## Manifest

Recorded in `config/project.yaml → datasets`. Fields marked *verify* come from public catalogue
pages and are checked against the downloaded file by `pipeline/01_inventory.py`.

| ID | Dataset | Nominal res. | Source | Identifier | Notes |
|---|---|---:|---|---|---|
| `ctx_ortho` | CTX Orthomosaic | 5 m (brief) | USGS Astrogeology | DOI 10.5066/P9GV1ND3 (Mars 2020 TRN CTX orthomosaic) | USGS documents ~6 m/pixel. The app always reports the **measured** pixel size. Confirm which product the "5 m" figure refers to. |
| `ctx_dem` | CTX DEM | 20 m | USGS Astrogeology | DOI 10.5066/P906QQT8 · `JEZ_ctx_B_soc_008_DTM_MOLAtopography_DeltaGeoid_20m_Eqc_latTs0_lon0.tif` | Catalogue lists radius 3 396 190 m, MOLA control. The vertical reference implied by "DeltaGeoid" must be confirmed from the label (step 06 report). |
| `hirise_dtm_1` | HiRISE DTM 1 | ~1 m | UA HiRISE / PDS | `DTEEC_…` — **to fill in** | Retains its own identity and footprint. |
| `hirise_dtm_2` | HiRISE DTM 2 | ~1 m | UA HiRISE / PDS | `DTEEC_…` — **to fill in** | Retains its own identity and footprint. |
| `themis_ti` | THEMIS Thermal Inertia | ~100 m | Edwards & Buz (2021), Zenodo | DOI 10.5281/zenodo.4931348 · `Jezero_Thermal_Inertia_v1.tiff` | Record states NoData = 0 and units J m⁻² K⁻¹ s⁻½; enforced via `nodata_override: 0`. |

> USGS catalogue entries for Jezero CTX products list different reference surfaces for different
> products (some sphere 3 396 190 m, some ellipsoid 3 396 190 / 3 376 200 m). This is exactly why
> step 02 parses each file's own CRS rather than assuming they match.

## Procedure

1. Download each product from its official source. Record the URL and date in
   `config/project.yaml` (`raw_filename`, `download_date`, optional publisher `sha256`).
2. Place files in `data/raw/`. Nothing else is ever written there except `SHA256SUMS`.
3. Run `pipeline/01_inventory.py`. It:
   - computes SHA-256 and writes `data/raw/SHA256SUMS` on first run; **aborts** on any later mismatch;
   - decodes every block of every band (detects truncated/corrupt downloads);
   - records driver, size, data type, CRS WKT, transform, pixel size, extent, NoData, units, tags, overviews;
   - removes write permission from raw files.
4. Run `pipeline/02_crs_validation.py` (CRS + coverage of the delta, see doc 02).

## Deliverables generated

| Brief deliverable | File |
|---|---|
| Dataset inventory | `data/reports/01-dataset-inventory.md`, `inventory.json` |
| Source & provenance | this document + `inventory.json` + provenance metadata embedded in every processed COG (`gdalinfo` → `JEZERO_*`) |
| SHA-256 checksums | `data/raw/SHA256SUMS` |
| CRS validation report | `data/reports/02-crs-validation.md` |
| Coverage & overlap report | `data/reports/05-coverage.md` |
| Vertical compatibility report | `data/reports/06-vertical.md` |
| Processing & reprojection report | `data/reports/03-reprojection.md`, `04-derivatives.md`, `07-alignment.md` |

## Rules enforced in code

- Raw files are opened read-only; outputs go to `processed/`.
- A file without a CRS is rejected unless an operator supplies `assigned_crs` **and**
  `assigned_crs_justification`, which is printed in the report.
- Output pixel size is never finer than the native ground pixel (no invented resolution).
- HiRISE layers are clipped to their own valid footprint; coverage outlines and percentages are shown in the UI.
