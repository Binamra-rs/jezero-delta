# Cloudflare Tunnel

The tunnel runs as the `cloudflared` container on the VPS (an always-on host —
a tunnel only *exposes* a running server, it does not host anything).

1. Cloudflare dashboard → Zero Trust → Networks → Tunnels → Create tunnel (cloudflared).
2. Copy the token into `deploy/.env` as `TUNNEL_TOKEN`.
3. Public hostname: `api.astro-mars.wiki` → Service `http://api:8000`.
4. The frontend (`astro-mars.wiki`) is served by Cloudflare Pages, not the tunnel.

Recommended Cloudflare settings for `api.astro-mars.wiki`:
- SSL/TLS: Full (strict); Always Use HTTPS on; HSTS on.
- Cache Rule: `URI Path starts with /api/v1/tiles/` → Eligible for cache, respect origin TTL.
- Rate limiting rule: `/api/v1/route` and `/api/v1/waypoints*`, e.g. 30 req / minute / IP.
