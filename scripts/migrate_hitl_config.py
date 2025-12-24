
import asyncio
import os
import sys
from sqlalchemy import text

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.config.database import async_engine

async def migrate_users_table():
    print("🔌 Connecting to database...")
    async with async_engine.begin() as conn:
        print("🏗️ Adding hitl_config column to users table if it doesn't exist...")
        try:
            # Check if column exists (PostgreSQL syntax)
            result = await conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='users' AND column_name='hitl_config';
            """))
            if not result.fetchone():
                await conn.execute(text("""
                    ALTER TABLE users ADD COLUMN hitl_config JSONB DEFAULT '{
                        "enabled": true, 
                        "mode": "denylist", 
                        "sensitive_tools": ["*google*", "*delete*", "*remove*", "*write*", "*-rm"],
                        "approval_message": "Execution requires your approval."
                    }';
                """))
                print("✅ Column 'hitl_config' added.")
            else:
                print("ℹ️ Column 'hitl_config' already exists.")
        except Exception as e:
            print(f"❌ Migration failed: {e}")

if __name__ == "__main__":
    asyncio.run(migrate_users_table())
