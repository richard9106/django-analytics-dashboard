#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${APP_DIR:-/home/deploy/apps/django-analytics-dashboard}"
OBJECT_KEY="${1:?Usage: restore_r2_backup_check.sh backups/postgres/nuviamy-...dump.gpg}"
WORK_DIR="$(mktemp -d)"
encrypted_path="$WORK_DIR/backup.dump.gpg"
dump_path="$WORK_DIR/backup.dump"

cleanup() { rm -rf "$WORK_DIR"; }
trap cleanup EXIT

cd "$APP_DIR"
env_value() { sed -n "s/^$1=//p" .env | head -1 | sed -e 's/^"//' -e 's/"$//'; }
export AWS_S3_ENDPOINT_URL="${AWS_S3_ENDPOINT_URL:-$(env_value AWS_S3_ENDPOINT_URL)}"
export AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-$(env_value AWS_ACCESS_KEY_ID)}"
export AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-$(env_value AWS_SECRET_ACCESS_KEY)}"
export AWS_STORAGE_BUCKET_NAME="${AWS_STORAGE_BUCKET_NAME:-$(env_value AWS_STORAGE_BUCKET_NAME)}"
export AWS_S3_REGION_NAME="${AWS_S3_REGION_NAME:-$(env_value AWS_S3_REGION_NAME)}"
export BACKUP_ENCRYPTION_PASSPHRASE="${BACKUP_ENCRYPTION_PASSPHRASE:-$(env_value BACKUP_ENCRYPTION_PASSPHRASE)}"

python3 - "$encrypted_path" "$OBJECT_KEY" <<'PY'
import os
import sys

import boto3

destination, object_key = sys.argv[1:]
client = boto3.client(
    's3',
    endpoint_url=os.environ['AWS_S3_ENDPOINT_URL'],
    aws_access_key_id=os.environ['AWS_ACCESS_KEY_ID'],
    aws_secret_access_key=os.environ['AWS_SECRET_ACCESS_KEY'],
    region_name=os.environ.get('AWS_S3_REGION_NAME', 'auto'),
)
client.download_file(os.environ['AWS_STORAGE_BUCKET_NAME'], object_key, destination)
PY

gpg --batch --yes --pinentry-mode loopback --passphrase "${BACKUP_ENCRYPTION_PASSPHRASE:?BACKUP_ENCRYPTION_PASSPHRASE is required}" --decrypt --output "$dump_path" "$encrypted_path"
./ops/verify_postgres_backup.sh "$dump_path"
echo "R2 restore verification passed: $OBJECT_KEY"
