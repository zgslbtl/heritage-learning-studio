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
                assert (await connection.execute(text("SELECT version_num FROM alembic_version"))).scalar_one() == "0017_recoverable_class_links"
                assert (await connection.execute(text("SELECT count(*) FROM information_schema.columns WHERE table_name='class_entry_links' AND column_name='token_scheme'"))).scalar_one() == 1
                definition = (await connection.execute(text("SELECT indexdef FROM pg_indexes WHERE indexname='uq_peer_batch_active'"))).scalar_one()
                assert "beta-continuous-v1" in definition and "class_id <> 0" in definition
                for table in ("runtime_tasks", "rate_limit_buckets", "participants"):
                    assert (await connection.execute(text("SELECT to_regclass(:table)"), {"table": table})).scalar_one()
                await connection.run_sync(Base.metadata.drop_all)
                await connection.execute(text("DROP TABLE alembic_version"))
        finally:
            await db.dispose()

    asyncio.run(inspect_and_clean())


def test_class_link_upgrade_preserves_existing_hashes(database_url, monkeypatch):
    import uuid
    from app.security import token_hash

    monkeypatch.setenv('DATABASE_URL', database_url)
    config = Config(str(Path(__file__).resolve().parents[1] / 'alembic.ini'))
    command.upgrade(config, '0016_hlsf_prompt_version')
    link_id = uuid.uuid4()
    digest = token_hash('legacy-migration-test-token')

    async def seed():
        db = Database(database_url)
        try:
            async with db.engine.begin() as conn:
                await conn.execute(text("INSERT INTO classes(id,name) VALUES (1,'Migration test')"))
                await conn.execute(text("INSERT INTO class_entry_links(id,class_id,token_hash,label,active,created_at) VALUES (:id,1,:digest,'Existing',true,now())"), {'id': link_id, 'digest': digest})
        finally:
            await db.dispose()

    asyncio.run(seed())
    command.upgrade(config, 'head')

    async def inspect_and_clean():
        db = Database(database_url)
        try:
            async with db.engine.begin() as conn:
                row = (await conn.execute(text('SELECT id,token_hash,token_scheme,active FROM class_entry_links'))).mappings().one()
                assert row['id'] == link_id and row['token_hash'] == digest
                assert row['token_scheme'] is None and row['active'] is True
                await conn.run_sync(Base.metadata.drop_all)
                await conn.execute(text('DROP TABLE alembic_version'))
        finally:
            await db.dispose()

    asyncio.run(inspect_and_clean())
