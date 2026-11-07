#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

if [[ ! -f .env ]]; then
  echo "ERROR: .env not found. Refusing to run without deployment configuration." >&2
  exit 1
fi

# shellcheck disable=SC1091
set -a
source .env
set +a

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DEST="${1:-$PROJECT_DIR/backups/$STAMP}"
mkdir -p "$DEST"
chmod 700 "$DEST"

DB_USER="${POSTGRES_USER:-heritage}"
DB_NAME="${POSTGRES_DB:-heritage}"

echo "Dumping PostgreSQL to $DEST/database.dump"
docker compose exec -T -e PGPASSWORD="${POSTGRES_PASSWORD:-}" db pg_dump -U "$DB_USER" -d "$DB_NAME" -Fc > "$DEST/database.dump"

echo "Archiving application data to $DEST/appdata.tar.gz"
docker compose exec -T api tar -C /data -czf - . > "$DEST/appdata.tar.gz"

cat > "$DEST/manifest.txt" <<EOF
Heritage Learning Studio backup
created_utc=$STAMP
database=$DB_NAME
database_format=pg_dump custom
appdata=/data
note=Environment files and credentials are NOT included. Back them up separately in a secure location.
EOF

if command -v sha256sum >/dev/null 2>&1; then
  (cd "$DEST" && sha256sum database.dump appdata.tar.gz > SHA256SUMS)
else
  (cd "$DEST" && shasum -a 256 database.dump appdata.tar.gz > SHA256SUMS)
fi

echo "Backup completed: $DEST"
echo "Copy it off-host and protect it. It contains research data."
