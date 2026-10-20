#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${APP_DIR:-/home/deploy/apps/django-analytics-dashboard}"
BACKUP_DIR="${BACKUP_DIR:-/home/deploy/backups/nuviamy/postgres}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
R2_PREFIX="${BACKUP_R2_PREFIX:-backups/postgres}"

umask 077
mkdir -p "$BACKUP_DIR"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_path="$BACKUP_DIR/nuviamy-$timestamp.dump"
temporary_path="$backup_path.partial"

cd "$APP_DIR"
env_value() { sed -n "s/^$1=//p" .env | head -1 | sed -e 's/^"//' -e 's/"$//'; }
export BACKUP_S3_BUCKET="${BACKUP_S3_BUCKET:-$(env_value BACKUP_S3_BUCKET)}"
export BACKUP_S3_PREFIX="${BACKUP_S3_PREFIX:-$(env_value BACKUP_S3_PREFIX)}"
export AWS_SESSION_TOKEN="${AWS_SESSION_TOKEN:-$(env_value AWS_SESSION_TOKEN)}"
export AWS_S3_ENDPOINT_URL="${AWS_S3_ENDPOINT_URL:-$(env_value AWS_S3_ENDPOINT_URL)}"
export AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-$(env_value AWS_ACCESS_KEY_ID)}"
export AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-$(env_value AWS_SECRET_ACCESS_KEY)}"
export AWS_STORAGE_BUCKET_NAME="${AWS_STORAGE_BUCKET_NAME:-$(env_value AWS_STORAGE_BUCKET_NAME)}"
export AWS_S3_REGION_NAME="${AWS_S3_REGION_NAME:-$(env_value AWS_S3_REGION_NAME)}"
export BACKUP_ENCRYPTION_PASSPHRASE="${BACKUP_ENCRYPTION_PASSPHRASE:-$(env_value BACKUP_ENCRYPTION_PASSPHRASE)}"
export POSTGRES_USER="${POSTGRES_USER:-$(env_value POSTGRES_USER)}"
export POSTGRES_DB="${POSTGRES_DB:-$(env_value POSTGRES_DB)}"

if [[ -n "$BACKUP_S3_BUCKET" ]]; then R2_PREFIX="${BACKUP_S3_PREFIX:-postgres}"; fi

docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$temporary_path"
test -s "$temporary_path"
mv "$temporary_path" "$backup_path"
find "$BACKUP_DIR" -type f -name 'nuviamy-*.dump' -mtime "+$RETENTION_DAYS" -delete

encrypted_path="$backup_path.gpg"
gpg --batch --yes --pinentry-mode loopback --passphrase-fd 3 --symmetric --cipher-algo AES256 --output "$encrypted_path" "$backup_path" 3<<< "${BACKUP_ENCRYPTION_PASSPHRASE:?BACKUP_ENCRYPTION_PASSPHRASE is required}"
python3 -m ops.backup_storage "$encrypted_path" "$R2_PREFIX/$(basename "$encrypted_path")"

rm -f "$encrypted_path"

echo "Created PostgreSQL backup: $backup_path"
