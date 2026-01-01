import os
import logging
from typing import Optional, AsyncGenerator, Generator
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base, sessionmaker
from backend.app.config import settings

logger = logging.getLogger(__name__)

# Single source of truth for Base
Base = declarative_base()

# Database configuration from settings
DATABASE_URL = settings.DATABASE_URL
POSTGRES_POOL_SIZE = settings.POSTGRES_POOL_SIZE
POSTGRES_MAX_OVERFLOW = settings.POSTGRES_MAX_OVERFLOW

# Async engine for async operations
async_engine = create_async_engine(
    DATABASE_URL,
    pool_size=POSTGRES_POOL_SIZE,
    max_overflow=POSTGRES_MAX_OVERFLOW,
    echo=False,
    pool_pre_ping=True,
)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Sync engine for migrations/background tasks
sync_database_url = DATABASE_URL.replace("+asyncpg", "")
sync_engine = create_engine(
    sync_database_url,
    pool_size=POSTGRES_POOL_SIZE,
    max_overflow=POSTGRES_MAX_OVERFLOW,
    echo=False,
)

# Sync session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=sync_engine,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency that provides a database session.
    Automatically handles commit/rollback and close.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

# Aliases for compatibility
get_async_session = get_db

def get_sync_session() -> Generator:
    """
    Get a sync database session.
    Automatically handles commit/rollback and close.
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


async def init_db():
    """
    Initialize database tables.
    Importing models here ensures they are registered with Base.metadata.
    """
    import backend.app.core.state.models # noqa: F401
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """Close database connections."""
    await async_engine.dispose()

