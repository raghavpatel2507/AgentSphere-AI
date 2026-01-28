
import asyncio
import os
import sys
import logging

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import text, inspect
from backend.app.core.config.database import async_engine, Base, Tenant, TenantConfig
from backend.app.core.state.models import Conversation, Message, User, MCPServerConfig

# Import all models to ensure they are registered with Base
# (Conversation and Message are already imported from backend.app.core.state.models)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("setup_database")

async def setup_database():
    """
    Initialize the database:
    1. Drop obsolete checkpointer tables (checkpoints, writes).
    2. Create missing tables (conversations, messages, tenants, etc.).
    """
    logger.info("🔌 Connecting to database...")
    
    async with async_engine.begin() as conn:
        # Inspect existing tables
        def get_existing_tables(sync_conn):
            inspector = inspect(sync_conn)
            return inspector.get_table_names()

        existing_tables = await conn.run_sync(get_existing_tables)
        logger.info(f"Existing tables: {existing_tables}")

        # 1. Drop obsolete tables
        tables_to_drop = ["checkpoints", "checkpoint_writes", "writes"]
        for table in tables_to_drop:
            if table in existing_tables:
                logger.warning(f"🗑️ Dropping obsolete table: {table}")
                await conn.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
        
        # 2. Create current schema
        logger.info("🏗️ Creating/Updating schema...")
        await conn.run_sync(Base.metadata.create_all)
        
        logger.info("✅ Database schema initialized.")

if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    try:
        asyncio.run(setup_database())
    except Exception as e:
        logger.error(f"❌ Setup failed: {e}")
        sys.exit(1)

