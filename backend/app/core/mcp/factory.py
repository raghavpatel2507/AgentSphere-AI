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
    # Helper to resolve value
    async def resolve_value(val: Any) -> Any:
        if isinstance(val, str) and "${" in val and "}" in val:
            # Handle multiple placeholders in one string if needed, 
            # but simple case: "${VAR}"
            import re
            pattern = re.compile(r"\$\{(.+?)\}")
            
            async def replace_match(match):
                var_name = match.group(1)
                return await _get_var_value(var_name, user_id, app_def)
            
            # If the whole string is exactly one placeholder, we might want to return 
            # the object (e.g. dict for auth), but usually placeholders are strings.
            if val.startswith("${") and val.endswith("}") and val.count("${") == 1:
                return await _get_var_value(val[2:-1], user_id, app_def)
            
            # For composite strings (e.g. "Bearer ${TOKEN}")
            result = val
            for match in pattern.finditer(val):
                placeholder = match.group(0)
                var_name = match.group(1)
                replacement = await _get_var_value(var_name, user_id, app_def)
                result = result.replace(placeholder, str(replacement))
            return result
            
        return val

    # Resolve "env"
    if "env" in config_template and isinstance(config_template["env"], dict):
        new_env = {}
        for k, v in config_template["env"].items():
            new_env[k] = await resolve_value(v)
        config_template["env"] = new_env

    # Resolve "url" (for SSE/httpx)
    if "url" in config_template:
        config_template["url"] = await resolve_value(config_template["url"])

    # Resolve "auth" (for httpx types mostly, or arguments)
    if "auth" in config_template:
        if isinstance(config_template["auth"], dict):
             new_auth = {}
             for k, v in config_template["auth"].items():
                 new_auth[k] = await resolve_value(v)
             config_template["auth"] = new_auth
        elif isinstance(config_template["auth"], str):
             resolved_auth = await resolve_value(config_template["auth"])
             # Only delete if it's explicitly empty AND wasn't a placeholder 
             # (or if we want to allow manager.py to inject it later)
             if not resolved_auth and not app_def.oauth_config:
                 del config_template["auth"]
             elif resolved_auth:
                 config_template["auth"] = resolved_auth
             # else: keep the placeholder or empty value for manager.py to handle
             
    return config_template

async def _get_var_value(var_name: str, user_id: str, app: Any) -> str:
    """
    Fetch value for a placeholder based on app registry metadata.
    """
    # 1. Check for OAuth Config
    if app.oauth_config:
        # A. Check Metadata Map (e.g. ZOHO_URL -> _server_url)
        if var_name in app.oauth_config.token_metadata_map:
            meta_key = app.oauth_config.token_metadata_map[var_name]
            # Use app.id for per-app token lookup
            token_metadata = await oauth_service.get_token_metadata(user_id, app.id)
            if token_metadata:
                return token_metadata.get(meta_key, "")
        
        # B. Check for Token/Credentials placeholders
        # We assume if it's an OAuth app and they ask for a 'TOKEN', they want the access token
        if any(keyword in var_name.upper() for keyword in ["TOKEN", "CREDENTIALS", "ACCESS_KEY"]):
            # Use app.id for per-app token lookup
            token = await oauth_service.get_valid_token(user_id, app.id)
            return token or ""
            
    # 2. Fallback to OS Env (for static keys like ACCUWEATHER_API_KEY)
    return os.getenv(var_name, "")
