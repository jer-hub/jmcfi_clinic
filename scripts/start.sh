#!/bin/sh
set -e

PORT="${PORT:-8080}"

exec daphne -b 0.0.0.0 -p "$PORT" backend.asgi:application
