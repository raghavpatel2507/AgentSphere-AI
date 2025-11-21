"""
Script to initialize a default tenant for CLI usage.

This script creates a default tenant in the database for local development
and CLI usage. In production, tenants should be created via the API.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import uuid
from sqlalchemy import select
from src.core.config.database import get_async_session, Tenant, init_db



async def create_default_tenant():
    """Create a default tenant for CLI usage."""
    
    # Initialize database tables
    print("Initializing database tables...")
    await init_db()
    print("✅ Database tables initialized")
    
    # Create default tenant
    async for session in get_async_session():
        # Check if default tenant already exists
        result = await session.execute(
            select(Tenant).where(Tenant.api_key == "dev_api_key_12345")
        )
        existing_tenant = result.scalar_one_or_none()
        
        if existing_tenant:
            print(f"✅ Default tenant already exists: {existing_tenant.name} (ID: {existing_tenant.id})")
            return existing_tenant.id
        
        # Create new default tenant
        default_tenant = Tenant(
            id=uuid.uuid4(),
            name="Default Tenant",
            api_key="dev_api_key_12345",
            is_active=True,
            extra_metadata={"environment": "development", "created_by": "init_script"}
        )
        
        session.add(default_tenant)
        await session.commit()
        await session.refresh(default_tenant)
        
        print(f"✅ Created default tenant: {default_tenant.name}")
        print(f"   Tenant ID: {default_tenant.id}")
        print(f"   API Key: {default_tenant.api_key}")
        
        return default_tenant.id


if __name__ == "__main__":
    print("=" * 60)
    print("AgentSphere-AI: Default Tenant Initialization")
    print("=" * 60)
    print()
    
    try:
        tenant_id = asyncio.run(create_default_tenant())
        print()
        print("=" * 60)
        print("✅ Initialization complete!")
        print("=" * 60)
        print()
        print("You can now use the chat system with the default tenant.")
        print(f"Default Tenant ID: {tenant_id}")
        print()
    except Exception as e:
        print()
        print("=" * 60)
        print("❌ Initialization failed!")
        print("=" * 60)
        print()
        print(f"Error: {str(e)}")
        print()
        print("Please ensure:")
        print("1. PostgreSQL is running")
        print("2. Database 'agentsphere' exists")
        print("3. DATABASE_URL in .env is correct")
        print()
        print("See DATABASE_SETUP.md for detailed setup instructions.")
        print()
        exit(1)
