
import asyncio
import sys
import os

sys.path.append(os.getcwd())

from sqlalchemy import delete
from backend.app.db import async_engine
from backend.app.core.state.models import MCPServerConfig
from sqlalchemy.ext.asyncio import AsyncSession

async def cleanup_zoho():
    print("Cleaning up 'zoho' entries...")
    async with AsyncSession(async_engine) as session:
        # Delete all 'zoho' entries
        await session.execute(
            delete(MCPServerConfig).where(MCPServerConfig.name == "zoho")
        )
        await session.commit()
        print("✅ Deleted all 'zoho' configurations.")

if __name__ == "__main__":
    asyncio.run(cleanup_zoho())
