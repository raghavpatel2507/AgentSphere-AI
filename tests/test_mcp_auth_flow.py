import asyncio
import sys
import logging
from pathlib import Path
import httpx

# Add backend to path to import core modules
backend_path = Path(__file__).parent.parent
sys.path.append(str(backend_path))

from backend.app.core.mcp.registry import SPHERE_REGISTRY
from backend.app.core.mcp.token_manager import TokenManager
from uuid import UUID

# Configure Logging
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger("AuthTest")
logger.setLevel(logging.INFO)

# User ID observed in logs (The one with Zoho token)
# You can change this if you are testing a different user
USER_ID = UUID("233fa0c5-2db2-4770-82e6-30b7f875fe33")
TENANT_ID = UUID("550e8400-e29b-41d4-a716-446655440000") # Default/Placeholder if needed

BASE_URL = "http://localhost:8000/api/v1"

async def verify_auth_flow():
    print(f"\n🚀 Starting MCP Auth Flow Verification for User: {USER_ID}")
    print("=" * 60)

    # 1. Identify Services requiring Auth
    auth_apps = [
        app for app in SPHERE_REGISTRY 
        if app.auth_fields or (app.config_template.get("custom_oauth") and app.config_template["custom_oauth"].get("enabled"))
    ]
    print(f"📋 Found {len(auth_apps)} services that require authentication:")
    for app in auth_apps:
        print(f"   - {app.name} (ID: {app.id})")
    print("-" * 60)

    # 2. Check Database for Tokens (Direct DB Access)
    print("\n💾 Step 1: Checking Database for Stored Tokens...")
    from backend.app.config import config
    print(f"   ℹ️  DB URL: {config.DATABASE_URL}")
    
    # DEBUG: List all tokens to see what exists
    from sqlalchemy import select
    from backend.app.db import async_engine
    from backend.app.core.state.models import OAuthToken
    from sqlalchemy.ext.asyncio import AsyncSession
    
    async with AsyncSession(async_engine) as session:
        result = await session.execute(select(OAuthToken))
        all_tokens = result.scalars().all()
        print(f"   ℹ️  Total Tokens in DB: {len(all_tokens)}")
        for t in all_tokens:
            print(f"       - Service: {t.service}, User: {t.user_id}")
            
    token_manager = TokenManager(user_id=USER_ID)
    
    db_tokens = {}
    
    for app in auth_apps:
        try:
            token = await token_manager.get_token(service=app.id)
            if token:
                scopes = token.get("scopes", "Unknown")
                print(f"   ✅ {app.name:<15} : Token FOUND (Scopes: {len(scopes) if isinstance(scopes, list) else 'Present'})")
                
                # DEBUG: Inspect GitHub Token specifically
                if app.id == "github":
                    print(f"      🔍 GitHub Token Debug:")
                    print(f"      - Expires At: {token.get('expires_at')}")
                    print(f"      - Has Access Token: {bool(token.get('access_token'))}")
                    print(f"      - Has Refresh Token: {bool(token.get('refresh_token'))}")
                    print(f"      - Scopes: {token.get('scopes')}")
                
                db_tokens[app.id] = True
            else:
                print(f"   ❌ {app.name:<15} : No Token")
                db_tokens[app.id] = False
        except Exception as e:
            print(f"   ⚠️  {app.name:<15} : DB Check Failed ({e})")
            db_tokens[app.id] = False

    # 3. Check Live Connection via MCPManager (Core Logic)
    print("\n🔌 Step 2: Verifying Active Tool Connection via MCPManager...")
    
    # We need to ensure we have an event loop for async
    from backend.app.core.mcp.manager import MCPManager
    
    manager = MCPManager(user_id=USER_ID)
    await manager.initialize()
    
    print(f"{'Service':<20} | {'DB Token':<10} | {'Connection Status'}")
    print("-" * 60)

    for app in auth_apps:
        has_token = db_tokens.get(app.id, False)
        status_msg = "⚪ Skipped (No Token)"
        
        if has_token:
            try:
                print(f"   🔄 Connecting to {app.name}...", end="\r")
                
                # Check config availability
                if app.id not in manager._server_configs:
                     status_msg = "⚠️  Config Missing in DB"
                else:
                    try:
                         # Connect with timeout to avoid hanging on browser open
                         await asyncio.wait_for(
                             manager._connect_single(app.id, manager._server_configs[app.id]),
                             timeout=10.0
                         )
                         status_msg = "✅ Connected Successfully"
                    except asyncio.TimeoutError:
                         status_msg = "❌ Timeout (Likely opened browser)"
                    except Exception as conn_err:
                         status_msg = f"❌ Connection Failed: {conn_err}"
            
            except Exception as e:
                 status_msg = f"❌ Error: {e}"
        
        print(f"{app.name:<20} | {'Yes' if has_token else 'No':<10} | {status_msg}")

    # Cleanup
    print("\n🧹 Cleaning up test connections...")
    try:
        await manager.cleanup()
    except:
        pass

if __name__ == "__main__":
    asyncio.run(verify_auth_flow())
