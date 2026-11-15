# 08 — Administration, backup and recovery

## Routine

| Task | Command (from `/opt/jezero-delta/deploy`) |
|---|---|
| Status | `docker compose ps` · `curl -s localhost:8000/readyz` |
| Logs | `docker compose logs --since 1h api` |
| Restart API | `docker compose restart api` |
| Count waypoints / workspaces | `psql -U jezero -c "SELECT count(*) FROM waypoints; SELECT count(*) FROM workspaces"` |
| Remove abandoned workspaces | `psql -U jezero -c "DELETE FROM workspaces WHERE last_seen_at < now() - interval '365 days'"` |

## Backups

- `jezero-backup.timer` runs `backup/backup.sh` nightly: an online SQLite backup of `/state/jezero.sqlite3`, verified with `PRAGMA integrity_check`,
  SHA-256 written, retention `BACKUP_RETENTION_DAYS`, optional `rclone` copy to R2 (`BACKUP_RCLONE_REMOTE`).
- Check: `systemctl list-timers jezero-backup.timer`, `ls -lh /srv/jezero/backups`.
- Rasters: `raw/` is immutable and checksummed — back it up once (e.g. to R2) and keep `SHA256SUMS`.
  `processed/` and `reports/` can always be regenerated with the pipeline.

## Recovery

| Scenario | Procedure |
|---|---|
| Accidental data change | `./backup/restore.sh /srv/jezero/backups/jezero-<ts>.sqlite3` (asks for confirmation, verifies checksum, stops API during restore) |
| Lost VPS | new VPS → steps 1–4 of doc 07 → restore raw data from off-site copy, verify with `sha256sum -c SHA256SUMS` → run pipeline → `restore.sh` latest backup |
| Corrupt processed raster | delete it, re-run the pipeline from step 03 |

Test a backup at least quarterly (any machine with Python):

```bash
python3 -c "import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); print(c.execute('PRAGMA integrity_check').fetchone()[0], c.execute('SELECT count(*) FROM waypoints').fetchone()[0], 'waypoints')" /srv/jezero/backups/<latest>.sqlite3
```

## Data / science changes

| Change | Steps |
|---|---|
| New dataset version | put file in `raw/` with a new name, update config, re-run pipeline from 01, review reports, restart API |
| New boundary | edit `boundary`, re-run from 02, restart API (waypoints outside the new boundary remain stored but cannot be edited) |
| Routing profile tuning | edit `routing.profiles`, run `scripts/validate_routing.py --dem …`, update doc 05, restart API |
