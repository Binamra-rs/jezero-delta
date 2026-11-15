# 12 — Free hosting (no credit card)

The VPS setup in [07-deployment.md](07-deployment.md) still works. This page describes a $0 alternative
that needs no server of your own and no credit card:

```
 Netlify / Vercel / Cloudflare Pages (free)          Render free web service
 ─────────────────────────────────────────           ────────────────────────────
 React app + /map/config.json                        FastAPI (Docker, 1 worker)
           + /map/coverage/*.geojson     ── HTTPS ─► inspect · route · raw images
           + /map/tiles/<layer>/z/x/y.webp            rasters from jezero-api-data.tar
 waypoints: browser localStorage                      (downloaded at build time)
```

* **The map works with no API.** Config, coverage outlines and every tile are static files pre-rendered by the
  API's own renderer (`backend/scripts/export_static.py`). The map loads instantly and costs nothing to serve.
* **The API handles only clicks:** point inspection, A\* routing and the NASA raw-image proxy. Render's free
  instance sleeps after ~15 min idle and takes up to a minute to wake. The app pings it on load, so it is usually
  awake by the first click. Free instances also have a monthly bandwidth allowance (5 GB on Render's free tier
  as of 2026), which is why tiles are not served from there.
* **Waypoints live in the browser** (`VITE_WAYPOINTS=local`), because free API hosts have no persistent disk and
  the SQLite file would be wiped on every sleep or redeploy. The Survival Hub export makes an offline copy.

Free-tier terms change. Check each provider's current pricing page before relying on these limits.

## 0. One-time local preparation

Run these on the machine that has the processed rasters (`data/processed`, from the pipeline):

```bash
conda activate jezero              # or the backend venv
cd backend

# a) static map data → frontend/public/map   (≈ 5 min on 4 cores; ≈ 15 000 files, ≈ 80 MB)
python scripts/export_static.py

# b) data bundle for the API → dist/jezero-api-data.tar   (≈ 490 MB)
python scripts/make_api_bundle.py
```

Re-run both whenever the pipeline output changes.

## 1. Put the project on GitHub

The deploy services build from a Git repository. Push this folder (`jezero-delta/`) as its own repository so that
`netlify.toml`, `render.yaml` and `frontend/` are at the paths the configs expect.

* `frontend/public/map/` (the exported tiles) **must be committed**: the frontend host serves exactly what is in
  the repo. It is thousands of small files and no single file comes near GitHub's 100 MB limit.
* Do **not** commit `data/` or `dist/` (already in `.gitignore` / too large).

Then publish the API data bundle as a release asset (free, ≤ 2 GB per file):

```bash
gh release create data-v2 dist/jezero-api-data.tar --title "API raster bundle v2" --notes "Crater-wide boundary"
# asset URL: https://github.com/<you>/<repo>/releases/download/data-v2/jezero-api-data.tar
```

## 2. API on Render (free web service)

1. Sign up at render.com with GitHub. The free instance type is advertised as needing no card; Render may
   occasionally ask some accounts for extra verification.
2. **New → Blueprint** → select the repository. `render.yaml` defines `jezero-api` (Docker, `plan: free`).
3. When prompted, set:
   * `JEZERO_DATA_URL` — the release-asset URL from step 1
   * `JEZERO_CORS_ORIGINS` — your frontend origin, e.g. `https://jezero-explorer.netlify.app`
     (fill it in after step 3; comma-separate several, no trailing slash)
4. Wait for the build (it downloads and unpacks the bundle), then open `https://<service>.onrender.com/readyz`.
   It should report `"rasters": true`.

The image (`deploy/render/Dockerfile`) runs a single Uvicorn worker, which fits the 512 MB free instance.
The same image runs on any Docker host, for example `docker build -f deploy/render/Dockerfile --build-arg JEZERO_DATA_URL=… .`.

## 3. Frontend on Netlify (or Vercel / Cloudflare Pages)

**Netlify:** *Add new site → Import from Git* → the repository. `netlify.toml` already sets base `frontend`,
build `npm ci && npm run build`, publish `dist` and `VITE_STATIC_BASE=/map`. Add one environment variable:

```
VITE_API_BASE = https://<service>.onrender.com
```

and redeploy. `public/_redirects` serves a transparent tile for any tile outside a layer's data. `public/_headers`
sets the security and cache headers.

**Vercel:** *Add New → Project* → the repository, **Root Directory = `frontend`**. `frontend/vercel.json` holds the
rewrites and headers. Set `VITE_STATIC_BASE=/map` and `VITE_API_BASE=…` under Environment Variables.

**Cloudflare Pages:** root directory `frontend`, build `npm ci && npm run build`, output `dist`, same two variables.
Pages allows at most 20 000 files per deployment. The current export is about 15 000, so it fits.

Map-only deployment: leave `VITE_API_BASE` empty. The map, layers and waypoints work. Inspect, routing and raw
images show a notice instead.

Finally, put the frontend URL into Render's `JEZERO_CORS_ORIGINS` (step 2.3) if you have not already.

## Routing limit on the free instance

A* needs about 180 bytes of RAM per DEM cell. The default budget of 1.5 M cells (≈ 330 MB peak) fits the 512 MB
instance and allows CTX routes up to roughly 14 km. Longer routes get a clear "choose closer points" message. On a
host with more memory, raise the budget with `JEZERO_ROUTE_MAX_CELLS` (for example 4000000 needs about 1 GB).

## 4. Checklist

| Check | Expected |
|---|---|
| Frontend loads with the API asleep | map and layers appear immediately |
| `…/map/config.json` | JSON with `"static": {…}` |
| `https://<service>.onrender.com/readyz` | `"rasters": true` |
| Click the map (Point tab) | values within ~1 min on a cold start, < 1 s afterwards |
| Browser console | no CORS errors (if there are, fix `JEZERO_CORS_ORIGINS`) |
