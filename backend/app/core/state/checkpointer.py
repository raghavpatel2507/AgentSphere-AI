"""
LangGraph Checkpointer for true pause-and-resume HITL.
Uses PostgreSQL via langgraph-checkpoint-postgres.

Manages the AsyncPostgresSaver lifecycle (setup/teardown) globally.
"""

import logging
from typing import Optional
from contextlib import asynccontextmanager
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from ...config import config

logger = logging.getLogger(__name__)

# Global singleton storage
_saver_context = None
_saver_instance: Optional[AsyncPostgresSaver] = None

async def initialize_checkpointer():
    """
    Initialize the global checkpointer instance.
    Expected to be called during app startup.
    """
    global _saver_context, _saver_instance
    
    db_url = config.DATABASE_URL
    # Fix asyncpg format for langgraph-checkpoint-postgres if needed
    # (The library uses psycopg3/asyncpg internally but connection string handling varies)
    # Actually langgraph-checkpoint-postgres typically handles the standard postgresql+asyncpg string fine,
    # or uses psycopg 3.
    # We'll use the one from config.
    
    logger.info("Initializing LangGraph checkpointer...")
    
    # Fix connection string for psycopg 3 (used by langgraph-checkpoint-postgres)
    # It expects postgresql:// not postgresql+asyncpg://
    if "postgresql+asyncpg" in db_url:
        db_url = db_url.replace("postgresql+asyncpg", "postgresql")
    
    try:
        # Create context manager
        _saver_context = AsyncPostgresSaver.from_conn_string(db_url)
        # Enter context manually to keep it open
        _saver_instance = await _saver_context.__aenter__()
        
        # Setup tables
        await _saver_instance.setup()
        logger.info("✅ Checkpointer ready")
        
    except Exception as e:
        logger.error(f"Failed to initialize checkpointer: {e}")
        # If we fail here, we might want to cleanup
        if _saver_context:
            await _saver_context.__aexit__(None, None, None)
            _saver_context = None
            _saver_instance = None
        raise

async def shutdown_checkpointer():
    """Cleanup checkpointer on app shutdown."""
    global _saver_context, _saver_instance
    
    if _saver_context:
        logger.info("Cleaning up checkpointer...")
        await _saver_context.__aexit__(None, None, None)
        _saver_context = None
        _saver_instance = None


def get_checkpointer() -> Optional[AsyncPostgresSaver]:
    """
    Get the active global checkpointer instance.
    Returns None if not initialized (should not happen if app started correctly).
    """
    return _saver_instance
