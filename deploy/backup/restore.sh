#!/usr/bin/env bash
# Restore a backup of the waypoint database. DESTRUCTIVE: replaces current data.
# Usage: ./backup/restore.sh /srv/jezero/backups/jezero-YYYYMMDDTHHMMSSZ.sqlite3
set -euo pipefail
cd "$(dirname "$0")/.."
backup="${1:?path to .sqlite3 backup}"
[[ -f "${backup}.sha256" ]] && sha256sum -c "${backup}.sha256"
read -r -p "This REPLACES all waypoints. Type RESTORE to continue: " ok
[[ "${ok}" == "RESTORE" ]] || { echo "aborted"; exit 1; }
docker compose stop api
docker compose cp "${backup}" api:/state/jezero.sqlite3
docker compose run --rm --no-deps api rm -f /state/jezero.sqlite3-wal /state/jezero.sqlite3-shm
docker compose start api
echo "restore complete"
