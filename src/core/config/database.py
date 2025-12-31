"""
Database configuration and connection management for AgentSphere-AI.

This module provides PostgreSQL connection utilities, SQLAlchemy setup,
and database schema definitions for multi-tenant support.
"""

import os
from typing import Optional
from sqlalchemy import create_engine, Column, String, Boolean, DateTime, JSON, UUID as SQLUUID
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.sql import func
from pathlib import Path
from dotenv import load_dotenv
import uuid

# Find project root (where .env is located)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
ENV_FILE = PROJECT_ROOT / ".env"
load_dotenv(dotenv_path=ENV_FILE)

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:root@localhost:5432/agentsphere")
POSTGRES_POOL_SIZE = int(os.getenv("POSTGRES_POOL_SIZE", "20"))
POSTGRES_MAX_OVERFLOW = int(os.getenv("POSTGRES_MAX_OVERFLOW", "10"))

# SQLAlchemy Base
Base = declarative_base()


# ============================================
# Database Engine and Session Management
# ============================================

# Async engine for async operations
async_engine = create_async_engine(
    DATABASE_URL,
    pool_size=POSTGRES_POOL_SIZE,
    max_overflow=POSTGRES_MAX_OVERFLOW,
    echo=False,  # Set to True for SQL logging
    pool_pre_ping=True,  # Verify connections before using
)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Sync engine for migrations
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


# ============================================
# Database Utilities
# ============================================

async def get_async_session() -> AsyncSession:
    """
    Get an async database session.
    
    Usage:
        async with get_async_session() as session:
            # Use session
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


def get_sync_session():
    """
    Get a sync database session.
    
    Usage:
        with get_sync_session() as session:
            # Use session
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
    Creates all tables defined in Base metadata.
    """
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """Close database connections."""
    await async_engine.dispose()

