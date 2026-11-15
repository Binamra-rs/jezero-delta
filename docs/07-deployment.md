# 07 — Production deployment

| Component | Host |
|---|---|
| Frontend `astro-mars.wiki` | Cloudflare Pages (static build) |
| API `api.astro-mars.wiki` | FastAPI in Docker on an always-on Linux VPS, exposed via Cloudflare Tunnel |
| Database | SQLite file `/state/jezero.sqlite3` on the persistent `state` volume (no DB server) |
| Rasters | VPS disk at `/srv/jezero/data` (mounted read-only into the API). Size guide: raw + processed ≈ 2–3× raw volume |
| Backups | nightly SQLite online backup (systemd timer), optional off-site copy to Cloudflare R2 |

Nothing runs on a developer machine. The tunnel only exposes the VPS — the VPS is the host.

## 1. VPS

Ubuntu 24.04, ≥ 4 vCPU, 8 GB RAM, SSD sized for the rasters (≥ 100 GB recommended).

```bash
sudo apt-get update && sudo apt-get install -y docker.io docker-compose-v2 git
sudo git clone <repo> /opt/jezero-delta && cd /opt/jezero-delta/deploy
sudo cp ../.env.example .env && sudo chmod 600 .env && sudoedit .env   # fill every value
sudo mkdir -p /srv/jezero/{data/raw,backups}
```

## 2. Data

Copy the five raw files to `/srv/jezero/data/raw/`, fill `raw_filename` (etc.) in `config/project.yaml`, then:

```bash
docker compose --profile pipeline run --rm pipeline     # runs steps 01–08
ls /srv/jezero/data/reports                            # review every report before going live
```

## 3. Cloudflare Tunnel

See `deploy/cloudflared/README.md`: create tunnel, put token in `.env`, route `api.astro-mars.wiki → http://api:8000`.

## 4. Start the stack

```bash
docker compose --env-file .env up -d --build    # api → cloudflared
curl -fsS http://127.0.0.1:8000/readyz
sudo cp systemd/*.service systemd/*.timer /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now jezero.service jezero-backup.timer
```

All services use `restart: unless-stopped`; `jezero.service` brings the stack up at boot. Verify with a
reboot (`sudo reboot`, then `./healthcheck.sh`).

## 5. Frontend (Cloudflare Pages)

- Connect the repository; **root directory** `frontend`; **build command** `npm ci && npm run build`;
  **output** `dist`.
- Environment variable `VITE_API_BASE=https://api.astro-mars.wiki` (the build fails if it is missing or points to localhost).
- Custom domain `astro-mars.wiki` (+ `www`). `public/_headers` sets CSP/security headers; `_redirects` handles SPA routes.

## 6. Cloudflare settings

- SSL/TLS Full (strict), Always Use HTTPS, HSTS.
- Cache rule for `api.astro-mars.wiki/api/v1/tiles/*` (respect origin `Cache-Control`). Tile URLs carry
  `?v=<catalog version>`, so re-running the pipeline busts caches automatically.
- Rate-limiting rule for `/api/v1/route` and `/api/v1/waypoints*` (the in-process limiter is per worker).

## 7. Monitoring and logs

- `docker compose logs -f api` — JSON lines with request id, path, status, latency.
- External uptime check of `deploy/healthcheck.sh` (or `/readyz`) every 5 min.
- Set `SENTRY_DSN` for error monitoring (PII disabled).

## 8. Updating

```bash
cd /opt/jezero-delta && git pull && cd deploy && docker compose --env-file .env up -d --build
```

The waypoint schema is created automatically when the API starts.
