#!/bin/sh
set -e

if [ "$RUN_MIGRATIONS" = "true" ]; then
    echo "[entrypoint] Running database migrations..."
    alembic upgrade head
fi

if [ "$SEED_DEMO_DATA" = "true" ]; then
    # Idempotent (ON CONFLICT DO NOTHING), safe on every start.
    echo "[entrypoint] Seeding Unit 100 demo data..."
    python -m scripts.seed_demo_data
fi

exec "$@"
