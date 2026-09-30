#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${APP_DIR:-/home/deploy/apps/django-analytics-dashboard}"
BACKUP_FILE="${1:?Usage: verify_postgres_backup.sh /path/to/backup.dump}"
TEMP_DB="nuviamy_restore_check_$(date -u +%Y%m%d%H%M%S)"
CONTAINER_BACKUP="/tmp/${TEMP_DB}.dump"

cd "$APP_DIR"
trap 'docker compose exec -T db sh -c "dropdb -U \"\$POSTGRES_USER\" --if-exists $TEMP_DB" >/dev/null 2>&1 || true; docker compose exec -T db rm -f "$CONTAINER_BACKUP" >/dev/null 2>&1 || true' EXIT

docker compose cp "$BACKUP_FILE" "db:$CONTAINER_BACKUP"
docker compose exec -T db sh -c "createdb -U \"\$POSTGRES_USER\" $TEMP_DB"
docker compose exec -T db sh -c "pg_restore -U \"\$POSTGRES_USER\" -d $TEMP_DB --no-owner --no-privileges --exit-on-error $CONTAINER_BACKUP"
docker compose exec -T db sh -c "psql -U \"\$POSTGRES_USER\" -d $TEMP_DB -tAc 'select count(*) from django_migrations'"
echo "Restore verification passed: $BACKUP_FILE"
