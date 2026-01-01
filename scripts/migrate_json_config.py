
import asyncio
import json
import os
import sys
import uuid

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.core.mcp.manager import MCPManager
from backend.app.core.config.database import async_engine
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.state.models import User, MCPServerConfig
from backend.app.core.auth.security import get_password_hash

async def migrate_config():
    # Use default IDs compatible with the rest of the app
    DEFAULT_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
    
    print(f"🚀 Starting migration for User: {DEFAULT_USER_ID}")
    
    # 1. Ensure Default User exists
    async with AsyncSession(async_engine) as session:
        user = await session.get(User, DEFAULT_USER_ID)
        if not user:
            print("👤 Creating default admin user...")
            user = User(
                id=DEFAULT_USER_ID,
                email="admin@agentsphere.ai",
                password_hash=get_password_hash("admin123"), # Default password
                full_name="Admin User"
            )
            session.add(user)
            await session.commit()
    
    # 2. Load JSON Config
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "multi_server_config.json")
    if not os.path.exists(config_path):
        print("ℹ️ No multi_server_config.json found. Nothing to migrate.")
        return

    with open(config_path, 'r') as f:
        config_data = json.load(f)
    
    mcp_servers = config_data.get("mcpServers", {})
    if not mcp_servers:
        print("ℹ️ mcpServers is empty. Nothing to migrate.")
        return

    # 3. Use MCPManager to save into DB (it handles encryption)
    manager = MCPManager(user_id=DEFAULT_USER_ID)
    
    for name, config in mcp_servers.items():
        print(f"📦 Migrating server: {name}")
        await manager._save_config_to_db(name, config)
    
    print("✅ Migration complete!")

if __name__ == "__main__":
    asyncio.run(migrate_config())

