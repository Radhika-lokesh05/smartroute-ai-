import asyncio
import os
import re
import sys
from urllib.parse import urlparse
import pytest
import pytest_asyncio
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text, pool
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.main import app
from app.core.config import settings
from app.core.database import get_db
from app.models.base import Base
import app.models  # Register all ORM models (AuditLog, Hospital, Ambulance, etc.) in Base.metadata

# Ensure Windows uses SelectorEventLoop to prevent SSL transport cleanup error on loop shutdown
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

_DB_INITIALIZED = False


def get_test_db_url() -> str:
    """Retrieve and strictly validate TEST_DATABASE_URL."""
    test_url = os.getenv("TEST_DATABASE_URL", settings.TEST_DATABASE_URL)
    if not test_url:
        pytest.skip(
            "TEST_DATABASE_URL is not configured. Set TEST_DATABASE_URL in .env to run DB integration tests.",
            allow_module_level=True,
        )
    if test_url == settings.DATABASE_URL:
        raise RuntimeError(
            "CRITICAL SAFETY VIOLATION: TEST_DATABASE_URL matches primary DATABASE_URL! "
            "Automated tests must never execute against DATABASE_URL."
        )
    return test_url


async def ensure_test_database_exists(test_url: str) -> None:
    """Ensure the test database exists; create it using the primary DATABASE_URL if missing."""
    parsed = urlparse(test_url)
    db_name = parsed.path.lstrip("/").split("?")[0]
    if not db_name or not re.match(r"^[a-zA-Z0-9_]+$", db_name):
        return

    # Check if test_url can already connect
    try:
        temp_engine = create_async_engine(test_url, poolclass=pool.NullPool)
        async with temp_engine.connect() as conn:
            await conn.execute(text("SELECT 1;"))
        await temp_engine.dispose()
        return
    except Exception as exc:
        err_msg = str(exc).lower()
        if "does not exist" not in err_msg and "invalidcatalogname" not in err_msg:
            return

    # Connect to primary DATABASE_URL with AUTOCOMMIT to create the test database
    maint_url = settings.DATABASE_URL
    maint_engine = create_async_engine(maint_url, isolation_level="AUTOCOMMIT", poolclass=pool.NullPool)
    try:
        async with maint_engine.connect() as conn:
            check_sql = text("SELECT 1 FROM pg_database WHERE datname = :dbname")
            exists = (await conn.execute(check_sql, {"dbname": db_name})).scalar()
            if not exists:
                await conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    except Exception as exc:
        print(f"[conftest] Auto-create test database notice: {exc}")
    finally:
        await maint_engine.dispose()


async def init_schema_once(url: str) -> None:
    """Run database creation and DDL migration once across all test runs."""
    global _DB_INITIALIZED
    if _DB_INITIALIZED:
        return

    await ensure_test_database_exists(url)

    engine = create_async_engine(url, poolclass=pool.NullPool)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
        await conn.run_sync(Base.metadata.create_all)
        # Ensure incremental columns and indexes are present if tables already existed
        await conn.execute(text("ALTER TABLE incidents ADD COLUMN IF NOT EXISTS note VARCHAR(200);"))
        await conn.execute(text("ALTER TABLE incidents ADD COLUMN IF NOT EXISTS expiry_reason VARCHAR(50);"))
        await conn.execute(text("ALTER TABLE incidents ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMP WITH TIME ZONE;"))
        await conn.execute(text("ALTER TABLE incidents ADD COLUMN IF NOT EXISTS resolved_by_id UUID REFERENCES users(id) ON DELETE SET NULL;"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_incidents_resolved_by_id ON incidents (resolved_by_id);"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_incidents_status_expires ON incidents (status, expires_at);"))
        await conn.execute(text("ALTER TABLE hospitals ADD COLUMN IF NOT EXISTS beds_simulated BOOLEAN DEFAULT TRUE;"))
        await conn.execute(text("ALTER TABLE hospitals ADD COLUMN IF NOT EXISTS emergency_types VARCHAR[] DEFAULT ARRAY['general']::varchar[];"))
        await conn.execute(text("ALTER TABLE hospitals ADD COLUMN IF NOT EXISTS is_24x7 BOOLEAN;"))
        await conn.execute(text("ALTER TABLE hospitals ADD COLUMN IF NOT EXISTS source VARCHAR(32) DEFAULT 'osm';"))
        await conn.execute(text("ALTER TABLE hospitals ADD COLUMN IF NOT EXISTS osm_attribution VARCHAR(255) DEFAULT '© OpenStreetMap contributors';"))
        await conn.execute(text("ALTER TABLE incidents ADD COLUMN IF NOT EXISTS is_simulated BOOLEAN DEFAULT FALSE;"))
        await conn.execute(text("ALTER TABLE dispatches ADD COLUMN IF NOT EXISTS is_simulated BOOLEAN DEFAULT FALSE;"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_incidents_is_simulated ON incidents (is_simulated);"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_dispatches_is_simulated ON dispatches (is_simulated);"))
    await engine.dispose()
    _DB_INITIALIZED = True


@pytest_asyncio.fixture
async def test_engine():
    """Function-scoped AsyncEngine matching current test event loop, using NullPool."""
    url = get_test_db_url()
    await init_schema_once(url)

    engine = create_async_engine(url, poolclass=pool.NullPool, echo=False)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Provide an isolated test database session and clean up rows after each test."""
    session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    async with session_factory() as session:
        yield session

        # Clean up all table rows in reverse dependency order
        try:
            await session.execute(text("DELETE FROM audit_log;"))
            await session.execute(text("DELETE FROM dispatches;"))
            await session.execute(text("DELETE FROM hospitals;"))
            await session.execute(text("DELETE FROM incident_votes;"))
            await session.execute(text("DELETE FROM incidents;"))
            await session.execute(text("DELETE FROM ambulances;"))
            await session.execute(text("DELETE FROM users;"))
            await session.commit()
        except Exception:
            await session.rollback()


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Standard HTTP test client for routes not requiring database overrides."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client


@pytest_asyncio.fixture
async def auth_client(test_engine, db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Authenticated and database-backed HTTP test client with fresh session per request."""
    session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client
    app.dependency_overrides.clear()
