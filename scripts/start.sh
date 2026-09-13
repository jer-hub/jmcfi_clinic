#!/bin/sh
set -e

PORT="${PORT:-8080}"

# Apply DB migrations on boot (safe no-op when already up to date).
python manage.py migrate --noinput

exec daphne -b 0.0.0.0 -p "$PORT" backend.asgi:application
