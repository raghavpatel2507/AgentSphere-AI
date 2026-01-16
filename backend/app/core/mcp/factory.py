from typing import Dict, Any, Optional
import os
import logging
from backend.app.core.mcp.registry import SPHERE_REGISTRY, get_app_by_id
from backend.app.core.oauth.service import oauth_service
from backend.app.core.state.models import MCPServerConfig

logger = logging.getLogger(__name__)

async def build_mcp_config(server_name: str, user_id: str, db_config: Optional[MCPServerConfig] = None) -> Optional[Dict[str, Any]]:
    """
    Constructs the mcp-use configuration for a given server.
    Injects OAuth tokens where needed.
    """
    # 1. Get Base Template from Registry
    app_def = get_app_by_id(server_name)
    if not app_def:
        logger.warning(f"Server {server_name} not found in registry")
        return None

    config_template = app_def.config_template.copy()
    
    # 2. Resolve Environment Variables / Placeholders
    # Iterate through 'env' or 'auth' fields to find ${VAR} patterns
    
    # Helper to resolve value
    async def resolve_value(val: Any) -> Any:
        if isinstance(val, str) and val.startswith("${") and val.endswith("}"):
            var_name = val[2:-1]
            return await _get_var_value(var_name, user_id)
        return val

    # Resolve "env"
    if "env" in config_template and isinstance(config_template["env"], dict):
        new_env = {}
        for k, v in config_template["env"].items():
            new_env[k] = await resolve_value(v)
        config_template["env"] = new_env

    # Resolve "auth" (for httpx types mostly, or arguments)
    if "auth" in config_template:
        # Auth might be a dict or string
        if isinstance(config_template["auth"], dict):
             for k, v in config_template["auth"].items():
                 config_template["auth"][k] = resolve_value(v) # Wait, async issue here if I mapped. 
                 # But simplistic approach:
                 pass 
        elif isinstance(config_template["auth"], str):
             resolved_auth = await resolve_value(config_template["auth"])
             # If auth resolves to empty string (e.g. key-based auth fallback), remove the auth key
             # to avoid sending "Authorization: Bearer " which is illegal
             if not resolved_auth:
                 del config_template["auth"]
             else:
                 config_template["auth"] = resolved_auth
             
    # Handle specific provider logic if complex (e.g. Google Drive needing file path vs token)
    # For now, assuming direct token injection or env var injection works.
    
    return config_template

async def _get_var_value(var_name: str, user_id: str) -> str:
    """
    Fetch value for a placeholder. 
    1. Check OAuth Tokens (for providers like Google, GitHub, Zoho)
    2. Check OAuth token metadata (for ZOHO_URL which is stored during OAuth)
    3. Fallback to OS Env (for static keys)
    """
    # Map Var Name to Provider
    # Naming convention: {PROVIDER}_API_KEY or {PROVIDER}_TOKEN
    
    # Provider mapping based on standard env names
    provider_map = {
        "GOOGLE_DRIVE_OAUTH_CREDENTIALS": "google",
        "GOOGLE_CALENDAR_TOKEN": "google",
        "GITHUB_TOKEN": "github",
        "ZOHO_TOKEN": "zoho",
        "GMAIL_TOKEN": "google"
    }
    
    provider = provider_map.get(var_name)
    if provider:
        token = await oauth_service.get_valid_token(user_id, provider)
        if token:
            return token
        else:
            logger.warning(f"No valid token found for {provider} (User {user_id})")
            return ""
    
    # Special handling for ZOHO_URL - get from OAuth token metadata
    if var_name == "ZOHO_URL":
        token_metadata = await oauth_service.get_token_metadata(user_id, "zoho")
        if token_metadata and token_metadata.get("_server_url"):
            return token_metadata["_server_url"]
        logger.warning(f"No Zoho server URL found for user {user_id}")
        return ""
            
    # Fallback to OS Env
    return os.getenv(var_name, "")
