"""
MCP Manager - Simplified Architecture.

Handles:
1. Configuration persistence (Database)
2. Server connection management (via mcp-use)
3. Tool retrieval (via langchain-mcp-adapters)

Refactored to remove redundant layers and confusing implementations.
"""

import os
import asyncio
import logging
import json
import shutil
import fnmatch
from typing import Dict, List, Any, Optional
from pathlib import Path

from mcp_use.client import MCPClient
from langchain_core.tools import StructuredTool
from langchain_mcp_adapters.tools import load_mcp_tools

from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.db import async_engine
from backend.app.core.state.models import User, MCPServerConfig
from backend.app.core.auth.security import decrypt_config, encrypt_config
from backend.app.config import PROJECT_ROOT

logger = logging.getLogger(__name__)


class MCPManager:
    """
    Manages MCP server connections and tools.
    Separates DB configuration from active connection state.
    """
    
    def __init__(self, user_id: Any):
        self.user_id = user_id
        
        # ACTOR 1: The MCP Client (Handles connections)
        self._client = MCPClient()
        self._sessions: Dict[str, Any] = {}
        
        # ACTOR 2: Configuration Cache
        self._server_configs: Dict[str, Dict] = {}
        self._hitl_config: Dict[str, Any] = {}

    @property
    def hitl_config(self) -> Dict[str, Any]:
        return self._hitl_config

    async def initialize(self):
        """Load config from DB (Do NOT connect automatically)."""
        await self._load_from_db()
        # await self._connect_all_enabled() # DISABLED lazy loading optimization


    # --------------------------------------------------------------------------
    # 1. Configuration / Database Layer
    # --------------------------------------------------------------------------
    
    async def _load_from_db(self):
        """Load all configs from database into memory."""
        async with AsyncSession(async_engine) as session:
            # Load User HITL Config
            user = await session.get(User, self.user_id)
            if user:
                self._hitl_config = user.hitl_config or {}

            # Load Server Configs
            result = await session.execute(
                select(MCPServerConfig).where(MCPServerConfig.user_id == self.user_id)
            )
            rows = result.scalars().all()
            
            self._server_configs = {}
            for row in rows:
                config = decrypt_config(row.config)
                
                # Attach metadata
                config["enabled"] = row.enabled
                config["disabled_tools"] = row.disabled_tools or []
                self._server_configs[row.name] = config

    async def save_server_config(self, name: str, config: Dict[str, Any]):
        """
        Save server configuration to database and update runtime state.
        
        Lifecycle:
        1. Disconnects any existing active session for this server (to ensure clean state).
        2. Persists the new configuration to the database (encrypted).
        3. Updates the local configuration cache.
        4. If the server is enabled, immediately initiates a new connection with the new config.
        """
        enabled = config.pop("enabled", True)
        disabled_tools = config.pop("disabled_tools", [])
        
        # 1. Runtime: Disconnect existing session if present
        # This ensures we don't have a lingering session with old credentials
        await self.disconnect_server(name)

        # Encrypt the entire config object
        encrypted_config = encrypt_config(config)
        
        # 2. Persistence: Save to DB
        async with AsyncSession(async_engine) as session:
            stmt = select(MCPServerConfig).where(
                MCPServerConfig.user_id == self.user_id,
                MCPServerConfig.name == name
            )
            row = (await session.execute(stmt)).scalar_one_or_none()
            
            if row:
                row.config = encrypted_config
                row.enabled = enabled
                row.disabled_tools = disabled_tools
                row.is_encrypted = True
            else:
                session.add(MCPServerConfig(
                    user_id=self.user_id,
                    name=name,
                    config=encrypted_config,
                    enabled=enabled,
                    disabled_tools=disabled_tools,
                    is_encrypted=True
                ))
            await session.commit()
        
        # 3. Cache: Update local cache
        config["enabled"] = enabled
        config["disabled_tools"] = disabled_tools
        self._server_configs[name] = config

        # 4. Runtime: Connect if enabled
        if enabled:
            try:
                import asyncio
                # Set a timeout so we don't hang the whole callback if mcp-use stalls
                await asyncio.wait_for(self._connect_single(name, config), timeout=15.0)
            except asyncio.TimeoutError:
                logger.error(f"⌛ Connection timeout for {name} during auto-config")
            except Exception as e:
                logger.error(f"❌ Failed to connect to {name} during auto-config: {e}")

    async def toggle_server_status(self, name: str, enabled: bool) -> bool:
        """Enable or disable a server."""
        if name not in self._server_configs:
            return False
            
        async with AsyncSession(async_engine) as session:
            stmt = select(MCPServerConfig).where(
                MCPServerConfig.user_id == self.user_id,
                MCPServerConfig.name == name
            )
            row = (await session.execute(stmt)).scalar_one_or_none()
            if row:
                row.enabled = enabled
                await session.commit()
                # Update cache
                self._server_configs[name]["enabled"] = enabled
                
                # Proactive management:
                if enabled:
                    # Sync connection so tools are available before response
                    await self._connect_single(name, self._server_configs[name])
                else:
                    # Disconnect immediately if disabled
                    await self.disconnect_server(name)
                
                return True
        return False
        
    async def remove_server(self, name: str) -> bool:
        """Fully remove a server: disconnect and delete config."""
        if name not in self._server_configs:
            return False
            
        await self.disconnect_server(name)
        await self.delete_server_config(name)
        return True

    async def delete_server_config(self, name: str):
        """Delete server from database."""
        async with AsyncSession(async_engine) as session:
            await session.execute(
                delete(MCPServerConfig).where(
                    MCPServerConfig.user_id == self.user_id, 
                    MCPServerConfig.name == name
                )
            )
            await session.commit()
        self._server_configs.pop(name, None)

    # --------------------------------------------------------------------------
    # 2. Connection Layer (mcp-use)
    # --------------------------------------------------------------------------

    async def connect_servers(self, server_names: List[str]):
        """Connect to specific list of servers."""
        tasks = []
        for name in server_names:
            if name in self._server_configs:
                config = self._server_configs[name]
                if config.get("enabled", True):
                   tasks.append(self._connect_single(name, config))
            else:
                logger.warning(f"Server {name} not found in config")
        
        if tasks:
            await asyncio.gather(*tasks)

    # Legacy method kept but unused to ensure clean API
    async def _connect_all_enabled(self):
        """Connect to all enabled servers in config."""
        tasks = []
        for name, config in self._server_configs.items():
            if config.get("enabled", True):
                tasks.append(self._connect_single(name, config))
        
        if tasks:
            await asyncio.gather(*tasks)

    async def _connect_single(self, name: str, config: Dict[str, Any]):
        """Connect a single server using mcp-use."""
        try:
            if name in self._sessions:
                return # Already connected

            # Use config directly (no environment resolution)
            resolved_config = config.copy()  # Copy to avoid modifying cache
            
            # Sanitize Auth: Remove empty auth/headers to avoid "Illegal header value"
            if "auth" in resolved_config and not resolved_config["auth"]:
                del resolved_config["auth"]

            # Windows fix
            if os.name == 'nt' and resolved_config.get("command") == "npx":
                resolved_config["command"] = "npx.cmd"

            # ------------------------------------------------------------------
            # Generic OAuth Credential Injection
            # ------------------------------------------------------------------
            from backend.app.core.mcp.registry import get_app_by_id
            app = get_app_by_id(name)
            if app and app.oauth_config and app.oauth_config.credential_files:
                await self._prepare_oauth_credentials(app, resolved_config, name)
            
            # ------------------------------------------------------------------
            # Direct Token Injection (e.g. Atlassian, GitHub)
            # Inject fresh OAuth tokens directly into 'auth' config for non-file apps
            # ------------------------------------------------------------------
            elif app and app.oauth_config and not app.oauth_config.credential_files:
                tmpl_auth = app.config_template.get("auth")
                if isinstance(tmpl_auth, str) and "${" in tmpl_auth:
                     from backend.app.core.oauth.service import oauth_service
                     creds = await oauth_service.get_full_credentials(self.user_id, app.id)
                     if creds and creds.get("token"):
                        resolved_config["auth"] = creds["token"]
                        logger.debug(f"Refreshed and injected direct OAuth token for {name}")

            # ------------------------------------------------------------------
            # Home/Env Spoofing
            # Only required for apps that use file-based credentials
            # ------------------------------------------------------------------
            if app and app.oauth_config and app.oauth_config.credential_files:
                temp_home = PROJECT_ROOT / "backend" / "temp" / "tokens" / str(self.user_id) / name
                temp_home.mkdir(parents=True, exist_ok=True)
                
                if "env" not in resolved_config:
                    resolved_config["env"] = {}
                
                # Isolate environment for file-based auth
                resolved_config["env"]["HOME"] = str(temp_home.absolute())
                resolved_config["env"]["USERPROFILE"] = str(temp_home.absolute())

            # mcp-use: Register then Connect
            # Sanitize config for logging
            log_config = resolved_config.copy()
            if "auth" in log_config:
                log_config["auth"] = "***"

            logger.info(f"Adding server to mcp-use: {name} with config: {json.dumps(log_config, default=str)}")
            self._client.add_server(name, resolved_config)
            
            logger.info(f"Creating session for {name}...")
            self._sessions[name] = await self._client.create_session(name)
            
            # Post-connect cleanup of temp files
            if app and app.oauth_config and app.oauth_config.credential_files:
                 self._cleanup_temp_files(app, name)
            
            logger.info(f"✅ Connected: {name}")
        except Exception as e:
            error_str = str(e).lower()
            is_auth_error = "401" in error_str or "unauthorized" in error_str or "oauthauthenticationerror" in type(e).__name__.lower()
            
            if is_auth_error:
                # Auth failure - delete stale token to force re-authentication on next attempt
                logger.warning(f"🔐 Authentication failed for {name}. Deleting stale token to trigger re-auth.")
                try:
                    from backend.app.core.oauth.service import oauth_service
                    from backend.app.db import AsyncSessionLocal
                    from backend.app.core.state.models import OAuthToken
                    from sqlalchemy import delete
                    
                    async with AsyncSessionLocal() as session:
                        await session.execute(
                            delete(OAuthToken).where(
                                OAuthToken.user_id == str(self.user_id),
                                OAuthToken.app_id == name
                            )
                        )
                        await session.commit()
                    logger.info(f"🗑️ Deleted stale token for {name}. User must re-authenticate.")
                except Exception as cleanup_error:
                    logger.error(f"Failed to cleanup stale token: {cleanup_error}")
                    
            logger.error(f"❌ Connection failed for {name}: {e}")
            import traceback
            logger.error(traceback.format_exc())

    async def _prepare_oauth_credentials(self, app: Any, resolved_config: Dict, server_name: str):
        """Generates temporary credential files based on app registry definitions."""
        from backend.app.core.oauth.service import oauth_service
        
        # 1. Fetch credentials using app.id for per-app token storage
        creds = await oauth_service.get_full_credentials(self.user_id, app.id)
        if not creds:
            logger.warning(f"No OAuth credentials found for app {app.id}")
            return

        # 2. Prepare Directory: Isolated by server_name
        base_dir = PROJECT_ROOT / "backend" / "temp" / "tokens" / str(self.user_id) / server_name
        base_dir.mkdir(parents=True, exist_ok=True)

        # 3. Process File Definitions
        for file_def in app.oauth_config.credential_files:
            # Handle subdirectories within tokens dir
            file_path = base_dir / file_def.filename
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Build Content
            if file_def.content_template == "__FULL_CREDS__":
                content = creds
            else:
                # Recursive string substitution in dict
                def substitute(val):
                    if isinstance(val, str):
                        # Special case: Entire value is a single placeholder "${key}"
                        # This allows returning objects (lists/dicts) directly
                        if val.startswith("${") and val.endswith("}") and val.count("${") == 1:
                            key = val[2:-1]
                            if key in creds:
                                return creds[key]
                        
                        # General case: Partial string substitution
                        for k, v in creds.items():
                            placeholder = f"${{{k}}}"
                            if placeholder in val:
                                val = val.replace(placeholder, str(v))
                        return val
                    elif isinstance(val, dict):
                        return {k: substitute(v) for k, v in val.items()}
                    elif isinstance(val, list):
                        return [substitute(item) for item in val]
                    return val
                
                content = substitute(file_def.content_template)

            # Write File
            with open(file_path, "w") as f:
                json.dump(content, f, indent=2)
            
            logger.info(f"Generated temp credential file for {server_name} ({app.id}): {file_path}")

            # 4. Inject into Config
            if "env" not in resolved_config:
                resolved_config["env"] = {}
            
            for env_var in file_def.env_vars:
                # Use forward slashes for paths to be safe with Node/JS on Windows
                path_str = str(file_path.absolute()).replace("\\", "/")
                resolved_config["env"][env_var] = path_str
            
            if file_def.inject_as_auth:
                resolved_config["auth"] = str(file_path.absolute()).replace("\\", "/")

    async def disconnect_server(self, name: str):
        """Disconnect active session."""
        if name in self._sessions:
            self._sessions.pop(name, None)
            
            # Cleanup temporary files
            from backend.app.core.mcp.registry import get_app_by_id
            app = get_app_by_id(name)
            if app:
                self._cleanup_temp_files(app, name)

    def _cleanup_temp_files(self, app: Any, server_name: str):
        """Clean up temporary credential files and any NPM/Node junk."""
        try:
            if not app.oauth_config or not app.oauth_config.credential_files:
                return

            # Completely remove the isolated server directory
            base_dir = PROJECT_ROOT / "backend" / "temp" / "tokens" / str(self.user_id) / server_name
            if base_dir.exists():
                # shutil.rmtree(base_dir, ignore_errors=True)
                logger.info(f"Skipped cleanup of isolated temp directory for {server_name}: {base_dir}")
            
            # Optional: remove user directory if empty
            user_dir = base_dir.parent
            if user_dir.exists() and not any(user_dir.iterdir()):
                try:
                    user_dir.rmdir() 
                except:
                    pass
        except Exception as e:
            logger.warning(f"Failed to cleanup temp files for {server_name}: {e}")

    async def restart_server(self, name: str):
        """Restart a specific server connection."""
        await self.disconnect_server(name)
        config = self._server_configs.get(name)
        if config and config.get("enabled", True):
            await self._connect_single(name, config)

    # --------------------------------------------------------------------------
    # 3. Tool Layer
    # --------------------------------------------------------------------------

    async def get_tools(self, server_names: Optional[List[str]] = None) -> List[StructuredTool]:
        """Get LangChain-ready tools from connected servers (optionally filtered)."""
        all_tools = []
        
        # Ensure target servers are connected
        targets = server_names if server_names else list(self._server_configs.keys())
        for name in targets:
            config = self._server_configs.get(name)
            if config and config.get("enabled", True) and name not in self._sessions:
                try:
                    await self._connect_single(name, config)
                except Exception as e:
                    logger.error(f"Failed to connect to {name} during get_tools: {e}")

        for name, session in self._sessions.items():
            # If explicit list provided, skip others
            if server_names and name not in server_names:
                continue

            config = self._server_configs.get(name, {})
            disabled_tools = config.get("disabled_tools", [])
            
            try:
                # Use standard adapter logic
                tools = await self._fetch_tools_from_session(name, session)
                
                for tool in tools:
                    if tool.name in disabled_tools:
                        continue
                    
                    # Wrap tool execution for self-healing auth and type safety
                    tool = self._wrap_tool_execution(tool, name)
                    all_tools.append(tool)
                    
            except Exception as e:
                logger.error(f"Error fetching tools for {name}: {e}")
                
        return all_tools

    async def _fetch_tools_from_session(self, name: str, session: Any) -> List[StructuredTool]:
        """Convert mcp-use session to LangChain tools."""
        
        # Simple adapter to make mcp-use session look like official python-sdk session
        # This allows load_mcp_tools to work
        class SimpleAdapter:
            def __init__(self, s): self.s = s
            async def list_tools(self, cursor=None): 
                # Robustly extract tools list
                res = await self.s.list_tools()
                tools_list = getattr(res, 'tools', res)
                if not isinstance(tools_list, list):
                    logger.warning(f"SimpleAdapter: list_tools for {name} returned non-list tools: {type(tools_list)}")
                    tools_list = []
                
                # Wrap list in object expected by load_mcp_tools adapter
                class Result: 
                    def __init__(self, t): self.tools = t; self.nextCursor = None
                return Result(tools_list)
            async def call_tool(self, name, arguments, **kwargs):
                return await self.s.call_tool(name, arguments)

        return await load_mcp_tools(SimpleAdapter(session))

    # --------------------------------------------------------------------------
    # 4. Status & management methods (for API)
    # --------------------------------------------------------------------------

    def _matches_pattern(self, name: str, patterns: List[str]) -> bool:
        for p in patterns:
            if fnmatch.fnmatch(name, p): return True
        return False

    async def get_all_tools_status(self) -> Dict[str, Any]:
        """Get flattened status of all tools for UI."""
        status = {}
        
        sensitive_patterns = self._hitl_config.get("sensitive_tools", [])
        
        for name, config in self._server_configs.items():
            is_enabled = config.get("enabled", True)
            connected = name in self._sessions
            
            server_tools = []
            
            try:
                if connected:
                    result = await self._sessions[name].list_tools()
                    # Robust handle: result might be a list or an object with .tools
                    if hasattr(result, 'tools'):
                        raw_tools = result.tools
                    elif isinstance(result, list):
                        raw_tools = result
                    else:
                        logger.warning(f"Unexpected tools format from {name}: {type(result)}")
                        raw_tools = []

                    for t in raw_tools:
                        is_disabled = t.name in config.get("disabled_tools", [])
                        is_hitl = self._matches_pattern(t.name, sensitive_patterns)
                        
                        server_tools.append({
                            "name": t.name,
                            "description": t.description,
                            "enabled": not is_disabled,
                            "hitl": is_hitl
                        })
            except Exception as e:
                logger.error(f"Failed to list tools for status {name}: {e}")

            status[name] = {
                "connected": connected,
                "enabled": is_enabled,
                "tools": server_tools
            }
        return status

    async def toggle_tool_status(self, tool_name: str, enabled: bool, server_name: str) -> str:
        """Enable/Disable a tool."""
        if server_name not in self._server_configs:
            raise ValueError(f"Server {server_name} not found")
            
        config = self._server_configs[server_name]
        disabled = config.get("disabled_tools", [])
        
        if not enabled:
            if tool_name not in disabled:
                disabled.append(tool_name)
        else:
            if tool_name in disabled:
                disabled.remove(tool_name)
                
        # Update DB
        async with AsyncSession(async_engine) as session:
            stmt = select(MCPServerConfig).where(
                MCPServerConfig.user_id == self.user_id,
                MCPServerConfig.name == server_name
            )
            row = (await session.execute(stmt)).scalar_one()
            row.disabled_tools = list(disabled) # Force update
            await session.commit()
            
        # Update cache
        config["disabled_tools"] = disabled
        return f"Tool {tool_name} {'enabled' if enabled else 'disabled'}"

    async def toggle_tool_hitl(self, tool_name: str, enabled: bool) -> str:
        """Add/remote tool from sensitive patterns."""
        sensitive = self._hitl_config.get("sensitive_tools", [])
        
        # Simplified logic: If enabling HITL, add exact match pattern.
        # If disabling, remove exact match. (Doesn't handle glob cleanup)
        
        if enabled:
            if tool_name not in sensitive:
                sensitive.append(tool_name)
        else:
            if tool_name in sensitive:
                sensitive.remove(tool_name)
            # Also try removing glob if specifically matching? 
            # Ideally we assume user manages precise patterns via this UI, 
            # or we might need smarter logic. For now strict exact match management.
            
        # Update DB
        async with AsyncSession(async_engine) as session:
            user = await session.get(User, self.user_id)
            if user:
                # Create a new dict to force SQLAlchemy change detection on JSONB
                new_config = dict(user.hitl_config or {})
                new_config["sensitive_tools"] = list(sensitive)
                user.hitl_config = new_config
                await session.commit()
                self._hitl_config = new_config

        return f"HITL {'enabled' if enabled else 'disabled'} for {tool_name}"

    # --------------------------------------------------------------------------
    # Helpers
    # --------------------------------------------------------------------------

    def _wrap_tool_execution(self, tool: StructuredTool, server_name: str) -> StructuredTool:
        """
        Wraps tool execution to provide:
        1. Self-Healing Auth: Retries on 401/Unauthorized errors by restarting the server connection.
        2. Type Safety: Forces string output to prevent 422 errors.
        """
        original_func = tool.coroutine
        
        async def wrapper(**kwargs):
            try:
                # --------------------------------------------------------------
                # 1. Attempt Execution
                # --------------------------------------------------------------
                
                # Fix specific tool quirks here if needed
                if "firecrawl" in tool.name and "sources" in kwargs:
                     kwargs["sources"] = [{"type": s} if isinstance(s, str) else s for s in kwargs["sources"]]
                
                result = await original_func(**kwargs)
                
            except Exception as e:
                # --------------------------------------------------------------
                # 2. Handle Authentication Failures (Self-Healing)
                # --------------------------------------------------------------
                error_msg = str(e).lower()
                is_auth_error = "401" in error_msg or "unauthorized" in error_msg or "authentication failed" in error_msg
                
                if is_auth_error:
                    logger.warning(f"🔄 Token expired for {server_name} during tool '{tool.name}'. Triggering self-healing refresh...")
                    
                    try:
                        # 1. Force Restart (Disconnect -> Reconnect)
                        # This triggers _connect_single -> get_full_credentials -> oauth_service.get_valid_token -> refresh_token
                        await self.restart_server(server_name)
                        
                        # 2. We need to get the tool function from the NEW session
                        # We can't just call original_func because it's bound to the OLD session/client
                        
                        logger.info(f"🔄 verifying new session for {server_name}...")
                        new_session = self._sessions.get(server_name)
                        if not new_session:
                             raise ValueError("Failed to re-establish session after restart")
                             
                        # 3. Find the tool in the new session to get the new callable
                        # This is a bit expensive but necessary to bind to the new authenticated session
                        new_tools_list = await self._fetch_tools_from_session(server_name, new_session)
                        new_tool = next((t for t in new_tools_list if t.name == tool.name), None)
                        
                        if not new_tool:
                             raise ValueError(f"Tool {tool.name} not found after restart")
                             
                        # 4. Retry Execution with new callable
                        logger.info(f"🔄 Retrying {tool.name} with refreshed token...")
                        result = await new_tool.coroutine(**kwargs)
                        
                    except Exception as retry_error:
                        # If retry fails, return original error or retry error
                        logger.error(f"❌ Self-healing failed for {server_name}: {retry_error}")
                        raise e # Raise the ORIGINAL error to show the auth failure to user if repair failed
                else:
                    # Not an auth error, just raise normally
                    raise e
            
            # --------------------------------------------------------------
            # 3. Type Safety / Output Normalization
            # --------------------------------------------------------------
            
            # Ensure string
            if not isinstance(result, str):
                if hasattr(result, 'content') and isinstance(result.content, str):
                    return result.content
                return str(result)
            return result
        
        return StructuredTool.from_function(
            name=tool.name,
            description=tool.description,
            coroutine=wrapper,
            args_schema=tool.args_schema,
            handle_tool_error=True, # Enable LLM self-healing on error
        )
