"""
PostgreSQL Checkpointer for LangGraph with multi-tenant support.

This module provides the PostgreSQL checkpointer instance for LangGraph
workflows, with connection pooling and tenant-scoped thread management.
"""

import asyncio
import os
from typing import Optional
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from dotenv import load_dotenv

load_dotenv()

# Global checkpointer instance and context manager
_checkpointer: Optional[AsyncPostgresSaver] = None
_checkpointer_cm = None
_initialized = False


async def init_checkpointer() -> AsyncPostgresSaver:
    """
    Initialize the PostgreSQL checkpointer.
    
    This should be called once at application startup.
    Creates the necessary checkpoint tables if they don't exist.
    
    Returns:
        AsyncPostgresSaver: The initialized checkpointer instance
    """
    global _checkpointer, _checkpointer_cm, _initialized
    
    if _initialized and _checkpointer is not None:
        return _checkpointer
    
    # Get database URL from environment
    database_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/agentsphere")
    
    # Convert asyncpg URL to psycopg format
    # langgraph-checkpoint-postgres v3.x uses psycopg, not asyncpg
    psycopg_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
    
    # Create the checkpointer context manager
    _checkpointer_cm = AsyncPostgresSaver.from_conn_string(psycopg_url)
    
    # Enter the context manager to get the actual checkpointer
    _checkpointer = await _checkpointer_cm.__aenter__()
    
    # Setup checkpoint tables (creates tables if they don't exist)
    await _checkpointer.setup()
    
    _initialized = True
    print("✅ PostgreSQL checkpointer initialized")
    
    return _checkpointer


def get_checkpointer() -> AsyncPostgresSaver:
    """
    Get the singleton checkpointer instance.
    
    Must call init_checkpointer() first before using this function.
    
    Returns:
        AsyncPostgresSaver: The checkpointer instance
        
    Raises:
        RuntimeError: If checkpointer not initialized
    """
    if _checkpointer is None or not _initialized:
        raise RuntimeError(
            "Checkpointer not initialized. Call init_checkpointer() first."
        )
    return _checkpointer


async def close_checkpointer():
    """Close the checkpointer and connection pool."""
    global _checkpointer, _checkpointer_cm, _initialized
    
    if _checkpointer_cm is not None:
        # Exit the context manager to close connections
        await _checkpointer_cm.__aexit__(None, None, None)
        
        _checkpointer_cm = None
        _checkpointer = None
        _initialized = False
        print("✅ PostgreSQL checkpointer closed")

