#!/usr/bin/env bash
# Called only after the exact main revision has passed CI.
set -euo pipefail
revision=${1:?Reviewed full revision required}
mode=${2:-Deploy}
[[ "$revision" =~ ^[a-f0-9]{40}$ ]] || exit 2
[[ "$mode" == Validate || "$mode" == Deploy ]] || exit 2
test "$(git rev-parse HEAD)" = "$revision"
test -z "$(git status --porcelain)"
if [[ "$mode" == Deploy ]]; then
    # An empty/unrestored destination must never be activated by CI.
    test -f /home/deploy/.config/nuviamy-production/enable-deployment
fi
docker compose config --quiet
docker compose build web
docker compose run --rm --no-deps web python manage.py check --deploy --fail-level WARNING
if [[ "$mode" == Validate ]]; then
    echo 'Candidate validated; database, running services and timers unchanged.'
    exit 0
fi
docker compose run --rm --no-deps migrate
docker compose run --rm --no-deps migrate python -m ops.postgres_roles grant
docker compose run --rm --no-deps web python -m ops.postgres_roles verify
docker compose up -d --no-build
docker compose restart web
for attempt in {1..15}; do
    if curl --fail --silent --show-error -H 'X-Forwarded-Proto: https' http://127.0.0.1:8000/health/ &&
       curl --fail --silent --show-error -H 'X-Forwarded-Proto: https' --output /dev/null http://127.0.0.1:8000/static/security-session.js; then
        exit 0
    fi
    sleep 2
done
exit 1
