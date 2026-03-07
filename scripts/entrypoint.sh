#!/usr/bin/env sh
# Entrypoint: run Alembic migrations (best-effort) then start uvicorn.
# Uvicorn starts regardless of migration failure — /health surfaces the DB status.
set -e

echo "Running Alembic migrations..."
python -m alembic upgrade head || echo "WARNING: Alembic migrations failed or skipped (DB may be unavailable). Continuing startup."

echo "Starting uvicorn..."
exec python -m uvicorn bots.lead_bot.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8001}" \
    --workers 1
