from __future__ import annotations

from typing import AsyncIterator
import ssl
import uuid
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def connection_options(url: str):
    value = make_url(url)
    if value.drivername in ("postgres", "postgresql"):
        value = value.set(drivername="postgresql+asyncpg")
    query = dict(value.query)
    sslmode = query.pop("sslmode", None)
    query.pop("channel_binding", None)
    options = {}
    if sslmode and sslmode != "disable":
        options["ssl"] = ssl.create_default_context()
    if value.host and value.host.endswith(".neon.tech"):
        options.update(prepared_statement_cache_size=0,
                       prepared_statement_name_func=lambda: f"__hls_{uuid.uuid4().hex}__")
    return value.set(query=query), options


class Database:
    def __init__(self, url: str, pool_size: int = 20, max_overflow: int = 20, null_pool: bool = False):
        normalized, connect_args = connection_options(url)
        pool_options = {"poolclass": NullPool} if null_pool else {
            "pool_size": pool_size, "max_overflow": max_overflow, "pool_timeout": 30,
        }
        self.engine: AsyncEngine = create_async_engine(
            normalized,
            connect_args=connect_args,
            pool_pre_ping=True,
            **pool_options,
        )
        self.session_factory = async_sessionmaker(
            self.engine, expire_on_commit=False, class_=AsyncSession
        )

    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self.session_factory() as session:
            yield session

    async def dispose(self) -> None:
        await self.engine.dispose()
