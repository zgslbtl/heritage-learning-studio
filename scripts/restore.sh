#!/usr/bin/env bash
set -euo pipefail

if [[ "${CONFIRM_RESTORE:-}" != "YES" ]]; then
  echo "Refusing to restore without CONFIRM_RESTORE=YES." >&2
  echo "Usage: CONFIRM_RESTORE=YES ./scripts/restore.sh /path/to/backup" >&2
  exit 2
fi

BACKUP_DIR="${1:-}"
if [[ -z "$BACKUP_DIR" || ! -d "$BACKUP_DIR" ]]; then
  echo "ERROR: provide an existing backup directory." >&2
  exit 2
fi
if [[ ! -f "$BACKUP_DIR/database.dump" || ! -f "$BACKUP_DIR/appdata.tar.gz" ]]; then
  echo "ERROR: backup must contain database.dump and appdata.tar.gz." >&2
  exit 2
fi

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"
if [[ ! -f .env ]]; then
  echo "ERROR: .env not found." >&2
  exit 1
fi
# shellcheck disable=SC1091
set -a
source .env
set +a

DB_USER="${POSTGRES_USER:-heritage}"
DB_NAME="${POSTGRES_DB:-heritage}"
ABS_BACKUP="$(cd "$BACKUP_DIR" && pwd)"

echo "WARNING: this replaces the live database and /data volume."
echo "Stopping the API to prevent writes..."
docker compose stop api

echo "Restoring PostgreSQL..."
docker compose exec -T -e PGPASSWORD="${POSTGRES_PASSWORD:-}" db pg_restore -U "$DB_USER" -d "$DB_NAME" --clean --if-exists --no-owner < "$ABS_BACKUP/database.dump"

echo "Restoring application files..."
docker compose run --rm --no-deps -T \
  -v "$ABS_BACKUP:/backup:ro" \
  api sh -c 'find /data -mindepth 1 -maxdepth 1 -exec rm -rf {} + && tar -xzf /backup/appdata.tar.gz -C /data'

echo "Starting API..."
docker compose start api
docker compose ps
echo "Restore completed. Verify /api/health/ready and the researcher console before reopening the study."
