from sqlalchemy.ext.asyncio import AsyncSession
from src.core.config.database import (
    async_engine,
    AsyncSessionLocal,
    Base,
    init_db as core_init_db,
    close_db as core_close_db
)

from backend.app.config import settings


async def get_db() -> AsyncSession:
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


async def init_db():
    """Initialize database tables."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """Close database connections."""
    await async_engine.dispose()
