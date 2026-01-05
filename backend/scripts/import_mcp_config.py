
import asyncio
import json
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from backend.app.db import async_engine
from backend.app.core.state.models import User, MCPServerConfig
from backend.app.core.auth.security import encrypt_config
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

async def import_config(user_email: str, config_path: str):
    print(f"🚀 Starting MCP Config Migration for {user_email}...")
    
    if not os.path.exists(config_path):
        print(f"❌ Config file not found: {config_path}")
        return

    async with AsyncSession(async_engine) as session:
        # Find user
        result = await session.execute(select(User).where(User.email == user_email))
        user = result.scalar_one_or_none()
        
        if not user:
            print(f"❌ User not found: {user_email}")
            return
            
        user_id = user.id
        
        # Optional: Clear existing configs to avoid stale unencrypted data
        print(f"🧹 Clearing existing MCP configs for {user_email}...")
        await session.execute(delete(MCPServerConfig).where(MCPServerConfig.user_id == user_id))
        await session.commit()
            
        # Load JSON
        with open(config_path, "r") as f:
            data = json.load(f)
            
        mcp_servers = data.get("mcpServers", {})
        if not mcp_servers:
            print("⚠️ No servers found in 'mcpServers' key.")
            return
            
        count = 0
        for name, config in mcp_servers.items():
            print(f"📦 Importing {name}...")
            
            # Check if exists
            stmt = select(MCPServerConfig).where(
                MCPServerConfig.user_id == user_id,
                MCPServerConfig.name == name
            )
            existing = (await session.execute(stmt)).scalar_one_or_none()
            
            # Encrypt full config
            encrypted_data = encrypt_config(config)
            print(f"DEBUG: Encrypted data keys: {list(encrypted_data.keys())}")
            
            if existing:
                print(f"🔄 Updating existing {name}...")
                existing.config = encrypted_data
                existing.is_encrypted = True
            else:
                print(f"✨ Creating new {name}...")
                new_cfg = MCPServerConfig(
                    user_id=user_id,
                    name=name,
                    config=encrypted_data,
                    is_encrypted=True,
                    enabled=True
                )
                session.add(new_cfg)
            count += 1
            
        await session.commit()
        print(f"✅ Successfully imported {count} servers for {user_email}!")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Import MCP configs from JSON to DB")
    parser.add_argument("--email", required=True, help="User email to import for")
    parser.add_argument("--file", default="../multi_server_config.json", help="Path to config file")
    
    args = parser.parse_args()
    
    # Run async
    asyncio.run(import_config(args.email, args.file))
