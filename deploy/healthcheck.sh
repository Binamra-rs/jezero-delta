#!/usr/bin/env bash
# External uptime probe (cron every 5 min or any monitor): checks public HTTPS end to end.
set -euo pipefail
API="${1:-https://api.astro-mars.wiki}"
curl -fsS --max-time 10 "${API}/readyz" > /dev/null
curl -fsS --max-time 10 -o /dev/null "${API}/api/v1/tiles/ctx_ortho/0/0/0.png"
echo "ok"
