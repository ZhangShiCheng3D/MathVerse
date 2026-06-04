#!/usr/bin/env bash
# Online (WAL-safe) backup of the SQLite DB, keeping 14 days of snapshots.
# sqlite3 ".backup" is a hot backup — safe while the API is serving.
# Cron example (host or a sidecar):  0 3 * * *  /app/scripts/backup_db.sh
set -euo pipefail

DB="${MATHVERSE_DB:-data/mathverse.db}"
OUT_DIR="${BACKUP_DIR:-data/backups}"
RETAIN_DAYS="${BACKUP_RETAIN_DAYS:-14}"

mkdir -p "$OUT_DIR"
STAMP="$(date -u +%Y%m%d-%H%M%S)"
DEST="$OUT_DIR/mathverse-$STAMP.db"

sqlite3 "$DB" ".backup '$DEST'"
find "$OUT_DIR" -name 'mathverse-*.db' -mtime "+$RETAIN_DAYS" -delete
echo "backup ok: $DEST"
