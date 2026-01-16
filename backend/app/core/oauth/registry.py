from dataclasses import dataclass
from typing import List, Optional

# OAuthProvider definition removed - using OAuthConfig from mcp.registry

from backend.app.core.mcp.registry import SPHERE_REGISTRY

# Keep dataclass for compatibility with existing service code? 
# OR just return the OAuthConfig object if it has compatible attributes.
# OAuthConfig is Pydantic, so it supports dot notation. 
# However, service.py expects `provider.client_id_env`. OAuthConfig has this.
# So we can just return OAuthConfig.

def get_provider(name: str):
    """
    Look up OAuth provider config from the main MCP registry.
    """
    for app in SPHERE_REGISTRY:
        if app.oauth_config and app.oauth_config.provider_name == name:
            return app.oauth_config
            
    # Fallback/Legacy lookup if needed, or return None
    return None
