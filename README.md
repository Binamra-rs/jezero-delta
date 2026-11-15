# Jezero Delta Explorer

Interactive, scientifically traceable exploration of **Jezero crater, Mars**: the western delta, crater floor, rim and inlet/outlet valleys.
CTX / HiRISE / THEMIS layers in one canonical Mars CRS, click-to-inspect of real pixel values,
terrain-aware A\* route estimates, and persistent waypoints.

```
 Cloudflare Pages ── astro-mars.wiki ──► React + OpenLayers (proj4 Mars CRS)
                                              │  HTTPS (JSON, PNG tiles)
 Cloudflare Tunnel ── api.astro-mars.wiki ──► FastAPI ─┬─ COG tile renderer (rasterio/GDAL)
                                                       ├─ point sampler (native pixels)
                                                       ├─ A* router (terrain cost grid)
                                                       └─ auth + waypoints ──► SQLite (one file)
 Raster pipeline (GDAL) ── raw/ (immutable) ──► processed/*.tif (COG, project CRS) + catalog.json + reports/
```

## Repository

| Path | Contents |
|---|---|
| `config/project.yaml` | **Single source of truth**: Mars CRS, project boundary, dataset manifest, layers, routing profiles |
| `pipeline/` | Reproducible raster pipeline, steps 01–08 (inventory → CRS validation → reprojection → derivatives → coverage → vertical → alignment → catalog) |
| `backend/jezero/` | FastAPI app: `crs.py`, `tilegrid.py`, `terrain.py`, `routing/` (cost, A\*, Dijkstra reference, stats, service), `raster/` (catalog, tiles, sampler), `auth.py`, `api/` |
| `backend/tests/` | pytest suite: CRS, tile grid, terrain derivatives, A\* vs Dijkstra, API smoke test |
| `frontend/` | React + TypeScript + Vite + OpenLayers + Tailwind + Zustand |
| `deploy/` | docker compose (API, Cloudflare Tunnel, pipeline), backups, systemd units |
| `docs/` | Scientific and operational documentation (see index below) |

## Quick start (development)

```bash
# 1. Raw data → data/raw/   (see docs/01-datasets-provenance.md for exact products)
# 2. Process (needs GDAL ≥ 3.6; easiest via the pipeline image)
docker build -f pipeline/Dockerfile -t jezero-pipeline .
docker run --rm -v "$PWD/data:/data" jezero-pipeline          # writes data/processed + data/reports

# 3. API (waypoints go to data/jezero.sqlite3, created on first start; override with JEZERO_DB_PATH)
cd backend && pip install -r requirements-dev.txt
uvicorn jezero.api.main:app --reload

# 4. Frontend
cd frontend && npm install && VITE_API_BASE=http://localhost:8000 npm run dev
```

Tests: `cd backend && pytest` · `python scripts/validate_routing.py` · `cd frontend && npm test`.
Production: **docs/07-deployment.md** (own VPS) or **docs/12-free-hosting.md** ($0: Netlify/Vercel + Render, no credit card).

## Documentation

1. [Datasets & provenance](docs/01-datasets-provenance.md)
2. [Canonical Mars CRS](docs/02-crs.md)
3. [Processing & reprojection](docs/03-processing.md)
4. [Terrain derivatives](docs/04-terrain-derivatives.md)
5. [A\* terrain routing](docs/05-astar-routing.md) · [validation results](docs/results/astar-validation.md)
6. [API reference](docs/06-api.md)
7. [Deployment](docs/07-deployment.md)
8. [Administration, backup & recovery](docs/08-admin.md)
9. [Performance](docs/09-performance.md)
10. [Acceptance criteria matrix](docs/10-acceptance.md)
12. [Free hosting (Netlify / Vercel + Render)](docs/12-free-hosting.md)

## Status of this hand-over

| Area | State |
|---|---|
| CRS maths, tile grid, Horn slope / hillshade / TRI, A\*, Dijkstra validation | Implemented and **tested** (58 tests pass; 240/240 A\* = Dijkstra cases) |
| Pipeline, API, DB schema, frontend, deployment | Implemented; **must be run against the real datasets and a real host** — see the acceptance matrix for each item still to demonstrate |
| Dataset identifiers for the two HiRISE DTMs and the CTX orthomosaic file name | **To be filled in** in `config/project.yaml` once the exact products are chosen |
| Project boundary | Whole crater: 77.10–78.06° E, 17.90–18.86° N (≈ 3 075 km²; CTX 100 %, THEMIS 91.5 %, each HiRISE DTM ≈ 2.4 %) |
