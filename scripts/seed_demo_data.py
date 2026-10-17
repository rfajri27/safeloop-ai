"""Load the demo data package's seed SQL into the configured PostgreSQL database.

Usage (from the repo root, after `alembic upgrade head`):
    python -m scripts.seed_demo_data [path/to/seed.sql]

The seed is idempotent (ON CONFLICT DO NOTHING, deterministic UUIDs), so it is
safe to re-run. Default path: safeloop-demo-data/data/sql/seed.sql
"""
import asyncio
import sys
from pathlib import Path

import asyncpg

from config.settings import env

DEFAULT_SEED = Path(__file__).resolve().parent.parent / "safeloop-demo-data/data/sql/seed.sql"
COUNT_TABLES = (
    "sites", "units", "process_nodes", "assets", "asset_links", "sensor_tags",
    "safeguards", "safeguard_dependencies", "hazop_rows", "hazop_row_safeguards",
    "hazop_recommendations", "risk_rule_sets", "users", "prompt_templates",
    "documents", "document_assets", "golden_items",
)


async def main(seed_path: Path) -> None:
    conn = await asyncpg.connect(
        host=env.db_host, port=env.db_port, user=env.db_user,
        password=env.db_pass, database=env.db_name,
    )
    try:
        # The file wraps itself in BEGIN/COMMIT; no args = simple query protocol.
        await conn.execute(seed_path.read_text(encoding="utf-8"))
        for table in COUNT_TABLES:
            count = await conn.fetchval(f'SELECT count(*) FROM "{table}"')
            print(f"{table:24} {count}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main(Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SEED))
