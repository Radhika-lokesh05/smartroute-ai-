import asyncio
from typing import AsyncGenerator, Tuple, Optional
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from app.core.config import settings

# Async SQLAlchemy Engine targeting PostgreSQL via asyncpg
engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=300,
)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that yields an async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def check_database_connection(timeout_seconds: float = 2.0) -> Tuple[bool, Optional[str]]:
    """
    Safely ping the database to verify connectivity.
    Does not crash if the database is unreachable, timing out, or misconfigured.
    Returns (is_connected: bool, message: Optional[str]).
    """
    try:
        async def _ping() -> None:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))

        await asyncio.wait_for(_ping(), timeout=timeout_seconds)
        return True, "Database connection operational"
    except asyncio.TimeoutError:
        return False, f"Database connection timed out after {timeout_seconds}s"
    except Exception as exc:
        # Gracefully handle unreachable host, invalid auth, network drop, etc.
        return False, f"Database unreachable: {type(exc).__name__}"
