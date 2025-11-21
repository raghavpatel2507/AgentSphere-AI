"""
Script to migrate JSON configuration files to PostgreSQL database.

This script helps migrate existing JSON config files (like gmail_token.json,
zoho_config.json) to the database for multi-tenant support.
"""

import asyncio
import sys
from pathlib import Path
import os

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.config.tenant_config import get_config_manager


async def migrate_configs():
    """Migrate JSON config files to database."""
    
    print("=" * 60)
    print("Configuration Migration to PostgreSQL")
    print("=" * 60)
    print()
    
    # Get tenant ID from environment or use default
    tenant_id = os.getenv("DEFAULT_TENANT_ID", "default")
    
    # Get the actual tenant ID from database
    config_manager = get_config_manager()
    tenant = await config_manager.get_tenant_by_api_key("dev_api_key_12345")
    
    if not tenant:
        print("❌ Default tenant not found. Please run scripts/init_default_tenant.py first.")
        return
    
    tenant_id = str(tenant.id)
    print(f"📝 Migrating configs for tenant: {tenant.name} (ID: {tenant_id})")
    print()
    
    # Define config files to migrate
    config_files = [
        {
            "path": "src/configs/gmail_token.json",
            "key": "gmail_credentials",
            "description": "Gmail OAuth credentials"
        },
        {
            "path": "src/configs/zoho_token.json",
            "key": "zoho_credentials",
            "description": "Zoho OAuth credentials"
        },
        # Add more config files here as needed
    ]
    
    migrated = 0
    skipped = 0
    
    for config in config_files:
        file_path = Path(config["path"])
        
        if file_path.exists():
            try:
                await config_manager.migrate_json_config_to_db(
                    tenant_id=tenant_id,
                    json_file_path=str(file_path),
                    config_key=config["key"]
                )
                print(f"   ✅ {config['description']}")
                migrated += 1
            except Exception as e:
                print(f"   ❌ Failed to migrate {config['path']}: {str(e)}")
                skipped += 1
        else:
            print(f"   ⏭️  Skipped {config['description']} (file not found)")
            skipped += 1
    
    print()
    print("=" * 60)
    print(f"Migration Complete: {migrated} migrated, {skipped} skipped")
    print("=" * 60)
    print()
    
    if migrated > 0:
        print("✅ Configurations are now stored in PostgreSQL!")
        print()
        print("Next steps:")
        print("1. Update your code to load configs from database")
        print("2. Use ConfigManager.get_tenant_config() to retrieve configs")
        print("3. Optionally delete the JSON files (keep backups!)")
        print()


if __name__ == "__main__":
    asyncio.run(migrate_configs())
