from collections.abc import AsyncGenerator
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
import ssl

import certifi
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _create_ssl_context() -> ssl.SSLContext:
    """Use certifi CA bundle — fixes macOS Python.org SSL verify failures with Neon."""
    return ssl.create_default_context(cafile=certifi.where())


def _normalize_database_url(database_url: str) -> tuple[str, dict[str, object]]:
    url = database_url
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)

    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    connect_args: dict[str, object] = {}

    # asyncpg does not accept libpq-style sslmode/channel_binding query params.
    if query.pop("sslmode", None) or query.pop("ssl", None):
        connect_args["ssl"] = _create_ssl_context()
    query.pop("channel_binding", None)

    clean_query = urlencode({key: values[0] for key, values in query.items()})
    clean_url = urlunparse(parsed._replace(query=clean_query))
    return clean_url, connect_args


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        settings = get_settings()
        if not settings.DATABASE_URL:
            raise RuntimeError("DATABASE_URL is not configured")
        database_url, connect_args = _normalize_database_url(settings.DATABASE_URL)
        _engine = create_async_engine(
            database_url,
            connect_args=connect_args,
            pool_pre_ping=True,
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    session_factory = get_session_factory()
    async with session_factory() as session:
        yield session
