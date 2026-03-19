#!/usr/bin/env bash
# backup_db.sh — Create timestamped backup of lumio.db, keep last 7.
# Usage: ./scripts/backup_db.sh
# Cron example (daily at 04:00):
#   0 4 * * * /path/to/lumio/scripts/backup_db.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DB_FILE="${PROJECT_DIR}/db/lumio.db"
BACKUP_DIR="${PROJECT_DIR}/db/backups"

if [ ! -f "$DB_FILE" ]; then
    echo "ERROR: Database not found at ${DB_FILE}" >&2
    exit 1
fi

mkdir -p "$BACKUP_DIR"

TIMESTAMP=$(date -u +"%Y%m%dT%H%M%SZ")
BACKUP_FILE="${BACKUP_DIR}/lumio_${TIMESTAMP}.db"

cp "$DB_FILE" "$BACKUP_FILE"
echo "Backup created: ${BACKUP_FILE}"

# Keep only the 7 most recent backups, delete older ones
ls -1t "${BACKUP_DIR}"/lumio_*.db 2>/dev/null | tail -n +8 | while read -r old; do
    rm -f "$old"
    echo "Deleted old backup: ${old}"
done

echo "Done. Current backups:"
ls -lh "${BACKUP_DIR}"/lumio_*.db 2>/dev/null || echo "  (none)"
