"""Async engine / session factory with per-request tenant context.

Tenant isolation is enforced twice:
  1. application level  -> every query goes through a repository that filters org_id
  2. database level     -> PostgreSQL RLS policies read ``app.org_id``
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import Settings, get_settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine(settings: Settings | None = None) -> AsyncEngine:
    global _engine
    if _engine is None:
        cfg = settings or get_settings()
        if cfg.app_env == "test":
            # a new event loop per test -> pooling would hand out connections
            # created on a closed loop, so tests use NullPool
            _engine = create_async_engine(
                cfg.database_url,
                echo=cfg.db_echo,
                poolclass=NullPool,
            )
        else:
            _engine = create_async_engine(
                cfg.database_url,
                echo=cfg.db_echo,
                pool_size=cfg.db_pool_size,
                max_overflow=cfg.db_max_overflow,
                pool_pre_ping=True,
            )
    return _engine


def get_session_factory(settings: Settings | None = None) -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(settings),
            expire_on_commit=False,
            autoflush=False,
        )
    return _session_factory


async def dispose_engine() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None


async def set_tenant(session: AsyncSession, org_id: uuid.UUID | None) -> None:
    """Bind the current transaction to a tenant (RLS)."""
    await session.execute(
        text("select set_config('app.org_id', :org, true)"),
        {"org": str(org_id) if org_id else ""},
    )


async def set_bypass_rls(session: AsyncSession, enabled: bool = True) -> None:
    """System level operations (seed, price sync, migrations) bypass tenant RLS."""
    await session.execute(
        text("select set_config('app.bypass_rls', :v, true)"),
        {"v": "on" if enabled else "off"},
    )


@asynccontextmanager
async def session_scope(
    *,
    org_id: uuid.UUID | None = None,
    bypass_rls: bool = False,
    settings: Settings | None = None,
) -> AsyncIterator[AsyncSession]:
    factory = get_session_factory(settings)
    async with factory() as session:
        if bypass_rls:
            await set_bypass_rls(session, True)
        if org_id is not None:
            await set_tenant(session, org_id)
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
