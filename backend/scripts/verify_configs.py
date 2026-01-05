
import asyncio
import sys
import json
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from backend.app.db import async_engine
from backend.app.core.state.models import MCPServerConfig
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

async def verify_configs():
    async with AsyncSession(async_engine) as session:
        result = await session.execute(select(MCPServerConfig).limit(5))
        configs = result.scalars().all()
        for c in configs:
            print(f"Server: {c.name}")
            print(f"Metadata: encrypted={c.is_encrypted}")
            # Show raw config keys
            if isinstance(c.config, dict):
                print(f"Config Keys: {list(c.config.keys())}")
                if "encrypted" in c.config:
                    print("✅ Found 'encrypted' key.")
                else:
                    print("❌ 'encrypted' key NOT found.")
            print("-" * 20)

if __name__ == "__main__":
    asyncio.run(verify_configs())
