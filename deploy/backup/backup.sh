#!/usr/bin/env bash
# Nightly backup of the SQLite waypoint database with retention and optional R2 copy.
# Run from deploy/:  ./backup/backup.sh   (installed as a systemd timer, see ../systemd)
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; source .env; set +a
mkdir -p "${BACKUP_DIR}"
ts=$(date -u +%Y%m%dT%H%M%SZ)
out="${BACKUP_DIR}/jezero-${ts}.sqlite3"
# online, consistent copy via SQLite's backup API (safe while the API is writing)
docker compose exec -T api python -c "import sqlite3,sys; s=sqlite3.connect('/state/jezero.sqlite3'); d=sqlite3.connect('/state/backup.part'); s.backup(d); d.close(); s.close()"
docker compose exec -T api python -c "import sqlite3; c=sqlite3.connect('/state/backup.part'); assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'"
docker compose cp api:/state/backup.part "${out}.part"
docker compose exec -T api rm -f /state/backup.part
mv "${out}.part" "${out}"
sha256sum "${out}" > "${out}.sha256"
find "${BACKUP_DIR}" -name 'jezero-*.sqlite3*' -mtime +"${BACKUP_RETENTION_DAYS:-30}" -delete
if [[ -n "${BACKUP_RCLONE_REMOTE:-}" ]]; then
  rclone copy "${out}" "${BACKUP_RCLONE_REMOTE}/" && rclone copy "${out}.sha256" "${BACKUP_RCLONE_REMOTE}/"
fi
echo "backup ok: ${out}"
