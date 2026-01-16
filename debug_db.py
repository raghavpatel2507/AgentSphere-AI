
import asyncio
import sys
import os

# Ensure we can import from backend
sys.path.append(os.getcwd())

from sqlalchemy import select
from backend.app.db import async_engine
from backend.app.core.state.models import MCPServerConfig
from backend.app.core.auth.security import decrypt_config

async def check_zoho_config():
    print("Checking DB for 'zoho' config...")
    async with async_engine.connect() as conn:
        # We need a session / direct execution
        from sqlalchemy.ext.asyncio import AsyncSession
        async with AsyncSession(async_engine) as session:
            result = await session.execute(
                select(MCPServerConfig).where(MCPServerConfig.name == "zoho")
            )
            server = result.scalar_one_or_none()
            
            if not server:
                print("❌ No 'zoho' server found in DB.")
            else:
                print(f"✅ Found 'zoho' server (ID: {server.id})")
                try:
                    config = decrypt_config(server.config)
                    print("--- DECRYPTED CONFIG ---")
                    print(config)
                    
                    auth_header = config.get("headers", {}).get("Authorization", "MISSING")
                    print(f"--- AUTH HEADER: {auth_header} ---")
                    
                    if "Bearer" in auth_header and len(auth_header) < 10:
                        print("⚠️  WARNING: Auth header looks empty/broken!")
                    elif "Bearer" not in auth_header and auth_header != "MISSING":
                         print("ℹ️  Auth header exists but no Bearer prefix (Custom?)")
                    elif auth_header == "MISSING":
                         print("ℹ️  No Authorization header (Correct for URL-only auth)")
                         
                except Exception as e:
                    print(f"❌ Failed to decrypt config: {e}")

if __name__ == "__main__":
    asyncio.run(check_zoho_config())
