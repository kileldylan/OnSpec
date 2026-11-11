#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

python Requora_backend/manage.py migrate --noinput

python Requora_backend/manage.py run_requora_worker &
worker_pid=$!

gunicorn Requora_backend.wsgi:application --bind "0.0.0.0:${PORT:-10000}" &
web_pid=$!

cleanup() {
  kill "$worker_pid" "$web_pid" 2>/dev/null || true
  wait "$worker_pid" 2>/dev/null || true
  wait "$web_pid" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

set +e
wait -n "$worker_pid" "$web_pid"
status=$?
set -e
exit "$status"