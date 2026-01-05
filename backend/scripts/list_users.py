
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from backend.app.db import async_engine
from backend.app.core.state.models import User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

async def list_users():
    async with AsyncSession(async_engine) as session:
        result = await session.execute(select(User))
        users = result.scalars().all()
        for u in users:
            print(u.email)

if __name__ == "__main__":
    asyncio.run(list_users())
