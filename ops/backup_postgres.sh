#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${APP_DIR:-/home/deploy/apps/django-analytics-dashboard}"
BACKUP_DIR="${BACKUP_DIR:-/home/deploy/backups/nuviamy/postgres}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"

umask 077
mkdir -p "$BACKUP_DIR"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_path="$BACKUP_DIR/nuviamy-$timestamp.dump"
temporary_path="$backup_path.partial"

cd "$APP_DIR"
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$temporary_path"
test -s "$temporary_path"
mv "$temporary_path" "$backup_path"
find "$BACKUP_DIR" -type f -name 'nuviamy-*.dump' -mtime "+$RETENTION_DAYS" -delete

echo "Created PostgreSQL backup: $backup_path"
