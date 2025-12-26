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
from dotenv import load_dotenv
import uuid

load_dotenv()

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:root@localhost:5432/agentsphere")
POSTGRES_POOL_SIZE = int(os.getenv("POSTGRES_POOL_SIZE", "20"))
POSTGRES_MAX_OVERFLOW = int(os.getenv("POSTGRES_MAX_OVERFLOW", "10"))

# SQLAlchemy Base
Base = declarative_base()


# ============================================
# Database Models
# ============================================

class Tenant(Base):
    """Tenant model for multi-tenant support."""
    __tablename__ = "tenants"

    id = Column(SQLUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    api_key = Column(String(255), unique=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    is_active = Column(Boolean, default=True, index=True)
    extra_metadata = Column(JSON, default={}, name="metadata")  # Renamed to avoid SQLAlchemy conflict



class TenantConfig(Base):
    """Tenant configuration model for storing per-tenant settings."""
    __tablename__ = "tenant_configs"

    id = Column(SQLUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(SQLUUID(as_uuid=True), nullable=False, index=True)
    config_key = Column(String(255), nullable=False)
    config_value = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())



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

