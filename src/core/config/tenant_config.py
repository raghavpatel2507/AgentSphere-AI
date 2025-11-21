"""
Tenant configuration management for multi-tenant support.

This module provides utilities to load, cache, and manage tenant-specific
configurations from PostgreSQL database instead of JSON files.
"""

import json
import os
from typing import Optional, Dict, Any
from functools import lru_cache
from sqlalchemy import select
from src.core.config.database import get_async_session, Tenant, TenantConfig


class ConfigManager:
    """
    Manages tenant configurations with database storage and caching.
    
    Configurations are stored in PostgreSQL and cached in memory for performance.
    """
    
    def __init__(self):
        """Initialize configuration manager."""
        self._cache: Dict[str, Dict[str, Any]] = {}
    
    async def get_tenant_by_api_key(self, api_key: str) -> Optional[Tenant]:
        """
        Get tenant by API key.
        
        Args:
            api_key: The tenant's API key
            
        Returns:
            Tenant object or None if not found
        """
        async for session in get_async_session():
            result = await session.execute(
                select(Tenant).where(
                    Tenant.api_key == api_key,
                    Tenant.is_active == True
                )
            )
            return result.scalar_one_or_none()
    
    async def get_tenant_config(
        self,
        tenant_id: str,
        config_key: str,
        default: Any = None
    ) -> Any:
        """
        Get a specific configuration value for a tenant.
        
        Args:
            tenant_id: The tenant ID
            config_key: The configuration key
            default: Default value if not found
            
        Returns:
            Configuration value or default
        """
        # Check cache first
        cache_key = f"{tenant_id}:{config_key}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # Load from database
        async for session in get_async_session():
            result = await session.execute(
                select(TenantConfig).where(
                    TenantConfig.tenant_id == tenant_id,
                    TenantConfig.config_key == config_key
                )
            )
            config = result.scalar_one_or_none()
            
            if config:
                value = config.config_value
                self._cache[cache_key] = value
                return value
            
            return default
    
    async def set_tenant_config(
        self,
        tenant_id: str,
        config_key: str,
        config_value: Any
    ):
        """
        Set a configuration value for a tenant.
        
        Args:
            tenant_id: The tenant ID
            config_key: The configuration key
            config_value: The configuration value (will be stored as JSON)
        """
        async for session in get_async_session():
            # Check if config exists
            result = await session.execute(
                select(TenantConfig).where(
                    TenantConfig.tenant_id == tenant_id,
                    TenantConfig.config_key == config_key
                )
            )
            config = result.scalar_one_or_none()
            
            if config:
                # Update existing
                config.config_value = config_value
            else:
                # Create new
                import uuid
                config = TenantConfig(
                    id=uuid.uuid4(),
                    tenant_id=tenant_id,
                    config_key=config_key,
                    config_value=config_value
                )
                session.add(config)
            
            await session.commit()
            
            # Update cache
            cache_key = f"{tenant_id}:{config_key}"
            self._cache[cache_key] = config_value
    
    async def get_all_tenant_configs(self, tenant_id: str) -> Dict[str, Any]:
        """
        Get all configurations for a tenant.
        
        Args:
            tenant_id: The tenant ID
            
        Returns:
            Dictionary of all configurations
        """
        async for session in get_async_session():
            result = await session.execute(
                select(TenantConfig).where(TenantConfig.tenant_id == tenant_id)
            )
            configs = result.scalars().all()
            
            return {
                config.config_key: config.config_value
                for config in configs
            }
    
    async def migrate_json_config_to_db(
        self,
        tenant_id: str,
        json_file_path: str,
        config_key: str
    ):
        """
        Migrate a JSON configuration file to database.
        
        Args:
            tenant_id: The tenant ID
            json_file_path: Path to JSON file
            config_key: Key to store the config under
        """
        if not os.path.exists(json_file_path):
            raise FileNotFoundError(f"Config file not found: {json_file_path}")
        
        with open(json_file_path, 'r') as f:
            config_data = json.load(f)
        
        await self.set_tenant_config(tenant_id, config_key, config_data)
        print(f"✅ Migrated {json_file_path} to database as '{config_key}'")
    
    def clear_cache(self, tenant_id: Optional[str] = None):
        """
        Clear configuration cache.
        
        Args:
            tenant_id: Optional tenant ID to clear cache for.
                      If None, clears entire cache.
        """
        if tenant_id:
            # Clear only this tenant's cache
            keys_to_remove = [
                key for key in self._cache.keys()
                if key.startswith(f"{tenant_id}:")
            ]
            for key in keys_to_remove:
                del self._cache[key]
        else:
            # Clear entire cache
            self._cache.clear()


# Global config manager instance
_config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """
    Get the global configuration manager instance.
    
    Returns:
        ConfigManager instance
    """
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager
