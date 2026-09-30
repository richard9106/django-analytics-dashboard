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
export AWS_S3_ENDPOINT_URL="${AWS_S3_ENDPOINT_URL:-$(env_value AWS_S3_ENDPOINT_URL)}"
export AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-$(env_value AWS_ACCESS_KEY_ID)}"
export AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-$(env_value AWS_SECRET_ACCESS_KEY)}"
export AWS_STORAGE_BUCKET_NAME="${AWS_STORAGE_BUCKET_NAME:-$(env_value AWS_STORAGE_BUCKET_NAME)}"
export AWS_S3_REGION_NAME="${AWS_S3_REGION_NAME:-$(env_value AWS_S3_REGION_NAME)}"
export BACKUP_ENCRYPTION_PASSPHRASE="${BACKUP_ENCRYPTION_PASSPHRASE:-$(env_value BACKUP_ENCRYPTION_PASSPHRASE)}"
export POSTGRES_USER="${POSTGRES_USER:-$(env_value POSTGRES_USER)}"
export POSTGRES_DB="${POSTGRES_DB:-$(env_value POSTGRES_DB)}"

docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$temporary_path"
test -s "$temporary_path"
mv "$temporary_path" "$backup_path"
find "$BACKUP_DIR" -type f -name 'nuviamy-*.dump' -mtime "+$RETENTION_DAYS" -delete

encrypted_path="$backup_path.gpg"
gpg --batch --yes --pinentry-mode loopback --passphrase "${BACKUP_ENCRYPTION_PASSPHRASE:?BACKUP_ENCRYPTION_PASSPHRASE is required}" --symmetric --cipher-algo AES256 --output "$encrypted_path" "$backup_path"
python3 - "$encrypted_path" "$R2_PREFIX/$(basename "$encrypted_path")" <<'PY'
import os
import sys

import boto3

encrypted_path, object_key = sys.argv[1:]
client = boto3.client(
    's3',
    endpoint_url=os.environ['AWS_S3_ENDPOINT_URL'],
    aws_access_key_id=os.environ['AWS_ACCESS_KEY_ID'],
    aws_secret_access_key=os.environ['AWS_SECRET_ACCESS_KEY'],
    region_name=os.environ.get('AWS_S3_REGION_NAME', 'auto'),
)
client.upload_file(encrypted_path, os.environ['AWS_STORAGE_BUCKET_NAME'], object_key)
print(f'Uploaded encrypted backup: {object_key}')
PY

rm -f "$encrypted_path"

echo "Created PostgreSQL backup: $backup_path"
