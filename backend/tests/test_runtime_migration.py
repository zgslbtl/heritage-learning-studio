from __future__ import annotations

import asyncio
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text

from app.db import Base, Database


def test_empty_database_upgrades_to_cloud_head(database_url, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", database_url)
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.upgrade(config, "head")

    async def inspect_and_clean():
        db = Database(database_url)
        try:
            async with db.engine.begin() as connection:
                assert (await connection.execute(text("SELECT version_num FROM alembic_version"))).scalar_one() == "0015_beta_peer_snapshots"
                definition = (await connection.execute(text("SELECT indexdef FROM pg_indexes WHERE indexname='uq_peer_batch_active'"))).scalar_one()
                assert "beta-continuous-v1" in definition and "class_id <> 0" in definition
                for table in ("runtime_tasks", "rate_limit_buckets", "participants"):
                    assert (await connection.execute(text("SELECT to_regclass(:table)"), {"table": table})).scalar_one()
                await connection.run_sync(Base.metadata.drop_all)
                await connection.execute(text("DROP TABLE alembic_version"))
        finally:
            await db.dispose()

    asyncio.run(inspect_and_clean())
