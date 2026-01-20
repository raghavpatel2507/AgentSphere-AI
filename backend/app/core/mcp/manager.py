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
import fnmatch
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional

from mcp_use.client import MCPClient
from langchain_core.tools import StructuredTool
from langchain_mcp_adapters.tools import load_mcp_tools

from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.db import async_engine
from backend.app.core.state.models import User, MCPServerConfig
from backend.app.core.auth.security import decrypt_config, encrypt_config
from backend.app.core.mcp.token_manager import TokenManager

logger = logging.getLogger(__name__)


class MCPManager:
    """
    Manages MCP server connections and tools.
    Separates DB configuration from active connection state.
    """
    
    def __init__(self, user_id: Any):
        self.user_id = user_id
        
        # Token Manager for per-user OAuth token isolation (database-only)
        self.token_manager = TokenManager(user_id)
        
        # ACTOR 1: The MCP Client (Handles connections)
        self._client = MCPClient()
        self._sessions: Dict[str, Any] = {}
        
        # ACTOR 2: Configuration Cache
        self._server_configs: Dict[str, Dict] = {}
        self._hitl_config: Dict[str, Any] = {}
        
        # ACTOR 3: Tool Cache (to prevent redundant API calls during polling)
        self._tools_cache: Dict[str, Dict[str, Any]] = {} # {name: {"tools": [], "timestamp": 0}}
        self._CACHE_TTL = 300 # 5 minutes cache for tools

    @property
    def hitl_config(self) -> Dict[str, Any]:
        return self._hitl_config

    async def initialize(self):
        """Load config from DB (Do NOT connect automatically)."""
        await self._load_from_db()
        await self._cleanup_user_token_files()  # Clean up any stale token files on startup
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
        """Save server configuration to database."""
        enabled = config.pop("enabled", True)
        disabled_tools = config.pop("disabled_tools", [])
        
        # Encrypt the entire config object
        encrypted_config = encrypt_config(config)
        
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
        
        # Update local cache
        config["enabled"] = enabled
        config["disabled_tools"] = disabled_tools
        self._server_configs[name] = config
        
        # Clear tool cache on config change
        if name in self._tools_cache:
            del self._tools_cache[name]

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
        """Fully remove a server: disconnect, delete config, and cleanup tokens."""
        if name not in self._server_configs:
            return False
        
        # Capture config before deletion for cleanup
        config = self._server_configs.get(name)
            
        await self.disconnect_server(name)
        
        # Delete OAuth token from database so user can re-authenticate/switch accounts
        await self.token_manager.delete_token(name)
        
        # Delete configuration
        await self.delete_server_config(name)
        
        # Cleanup filesystem artifacts (mcp-use files)
        if config:
            await self._cleanup_filesystem_artifacts(name, config)
            
        return True

    async def _cleanup_filesystem_artifacts(self, name: str, config: Dict[str, Any]):
        """
        Remove physical files created by mcp-use in ~/.mcp_use/
        
        Retries logic to handle different naming conventions or sanitization.
        """
        try:
            mcp_dir = Path.home() / ".mcp_use"
            if not mcp_dir.exists():
                return
                
            # candidate identifiers to search for in filenames
            identifiers = [name, f"{name}_{self.user_id}"]

            # Also add name with underscore instead of dash (common in python module names)
            if "-" in name:
                identifiers.append(name.replace("-", "_"))
                identifiers.append(f"{name.replace('-', '_')}_{self.user_id}")
            
            # If http/https url is present, add sanitized versions
            # mcp-use often sanitizes URLs like: https://example.com/api -> example.com__api
            if "url" in config or ("config" in config and "url" in config["config"]):
                # Handle both direct url or nested in config (depending on structure)
                url = config.get("url") or config.get("config", {}).get("url")
                if url and isinstance(url, str):
                    # Remove protocol
                    no_proto = url.replace("https://", "").replace("http://", "")
                    
                    # Variation 1: Replace all / with _
                    v1 = no_proto.replace("/", "_")
                    
                    # Variation 2: Replace all / with __
                    v2 = no_proto.replace("/", "__")
                    
                    # Variation 3: First / to __, rest to _ (observed in mcp-use/registrations)
                    parts = no_proto.split("/", 1)
                    if len(parts) > 1:
                        v3 = f"{parts[0]}__{parts[1].replace('/', '_')}"
                        identifiers.append(v3)
                    
                    identifiers.extend([no_proto, v1, v2])

            logger.info(f"🧹 Cleaning up filesystem artifacts for {name} using identifiers: {identifiers}")

            # Define paths to check
            paths_to_clean_dirs = [
                mcp_dir / "tokens",
                mcp_dir / "tokens" / "registrations"
            ]
            
            for path in paths_to_clean_dirs:
                if not path.exists():
                    continue
                    
                for file_path in path.iterdir():
                    if not file_path.is_file():
                        continue
                        
                    is_match = False
                    fname = file_path.name.lower()
                    
                    for ident in identifiers:
                        clean_ident = ident.lower()
                        if clean_ident in fname:
                            is_match = True
                            break
                    
                    if is_match:
                        try:
                            file_path.unlink()
                            logger.info(f"   Deleted artifact: {file_path}")
                        except Exception as e:
                            logger.error(f"   Failed to delete {file_path}: {e}")
            
            # Also clean up the isolated sphere directory
            isolated_dir = Path.home() / ".sphere" / "mcp_data" / str(self.user_id) / name
            if isolated_dir.exists():
                import shutil
                shutil.rmtree(isolated_dir, ignore_errors=True)
                logger.info(f"   Deleted isolated directory: {isolated_dir}")

        except Exception as e:
            logger.error(f"Error during filesystem cleanup for {name}: {e}")

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

    async def _cleanup_user_token_files(self):
        """
        Delete ALL token files from .mcp_use directory.
        
        This ensures database is the only token source, regardless of how
        mcp-use names the token files (user-specific OR URL-based).
        
        Why aggressive cleanup:
        - mcp-use creates URL-based token files (e.g., api.githubcopilot.com__mcp.json)
        - These bypass our user-specific naming (github_{user_id}.json)
        - Shared across all users, causing OAuth to skip authorization
        """
        try:
            mcp_use_token_dir = Path.home() / ".mcp_use" / "tokens"
            if not mcp_use_token_dir.exists():
                return
            
            # Delete ALL .json files (aggressive cleanup)
            deleted_count = 0
            
            for token_file in mcp_use_token_dir.glob("*.json"):
                try:
                    token_file.unlink()
                    logger.info(f"🧹 Startup cleanup: Deleted {token_file.name}")
                    deleted_count += 1
                except Exception as e:
                    logger.warning(f"Failed to delete {token_file.name}: {e}")
            
            if deleted_count > 0:
                logger.info(f"✅ Cleaned up {deleted_count} token file(s) on startup")
            else:
                logger.debug(f"No token files found to clean up")
                    
        except Exception as e:
            logger.error(f"Error during startup token cleanup: {e}")

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
        """Connect a single server using mcp-use with user-specific OAuth tokens."""
        try:
            # Multi-user isolation: use a unique name for each user's server connection
            # This ensures mcp-use creates separate token files in ~/.mcp_use/tokens/
            mcp_use_name = f"{name}_{self.user_id}"
            
            if mcp_use_name in self._sessions:
                return # Already connected
                
            # Clear tool cache for this server on new connection
            if name in self._tools_cache:
                del self._tools_cache[name]

            # Clone config to avoid modifying cached version
            resolved_config = config.copy()

            # ROBUSTNESS FIX: Inject latest OAuth config from registry
            # This ensures even stale DB configs get the correct OAuth parameters
            try:
                from backend.app.core.mcp.registry import get_app_by_id
                reg_app = get_app_by_id(name)
                if reg_app and reg_app.config_template:
                    reg_oauth = reg_app.config_template.get("custom_oauth")
                    if reg_oauth:
                        logger.info(f"🔧 [Manager] Patching {name} with latest registry OAuth config")
                        resolved_config["custom_oauth"] = reg_oauth
                    
                    # Also sync use_pkce if present
                    if reg_app.config_template.get("use_pkce"):
                        resolved_config["use_pkce"] = True
            except Exception as e:
                logger.warning(f"Failed to patch registry config for {name}: {e}")
            
            # Special handling for Google services (Gmail, GDrive) with custom OAuth
            is_oauth_server = "custom_oauth" in resolved_config or resolved_config.get("use_pkce")
            # is_google_service = name in ["gmail-mcp", "google-drive", "google-calendar"] or "custom_oauth" in resolved_config
            # FIX: Only treat specific Google apps as Google services to avoid hijacking other OAuth tools (like GitHub)
            is_google_service = name in ["gmail-mcp", "google-drive", "google-calendar"]
            
            if is_google_service:
                logger.info(f"🔍 Google service detected ({name}) for user_id={self.user_id} - checking for tokens in database")
                token_data = await self.token_manager.get_token(name)
                
                if token_data and token_data.get("access_token"):
                    logger.info(f"✅ Found {name} tokens in database for user_id={self.user_id}")
                    try:
                        # Calculate expiry_date safely
                        expiry_date = None
                        if token_data.get("expires_at"):
                            try:
                                if isinstance(token_data["expires_at"], str):
                                    dt = datetime.fromisoformat(token_data["expires_at"].replace('Z', '+00:00'))
                                    expiry_date = int(dt.timestamp() * 1000)
                                else:
                                    expiry_date = int(token_data["expires_at"].timestamp() * 1000)
                            except:
                                expiry_date = int((datetime.utcnow() + timedelta(hours=1)).timestamp() * 1000)
                        elif token_data.get("expires_in"):
                            expiry_date = int((datetime.utcnow() + timedelta(seconds=token_data.get("expires_in"))).timestamp() * 1000)
                        else:
                            expiry_date = int((datetime.utcnow() + timedelta(hours=1)).timestamp() * 1000)

                        import json
                        # Determine credential path based on service name and user ID for isolation
                        # Path: ~/.sphere/mcp_data/{user_id}/{name}/
                        cred_dir = Path.home() / ".sphere" / "mcp_data" / str(self.user_id) / name
                        cred_dir.mkdir(parents=True, exist_ok=True)
                        
                        cred_path = cred_dir / "credentials.json"
                        tokens_path = cred_dir / "tokens.json"
                        
                        # 1. Write Credentials File (Client Secrets)
                        # We try to get client secrets from registry
                        from backend.app.core.mcp.registry import get_app_by_id
                        registry_app = get_app_by_id(name)
                        custom_oauth = registry_app.config_template.get("custom_oauth", {}) if registry_app else {}
                        
                        if custom_oauth:
                            client_id = custom_oauth.get("client_id")
                            client_secret = custom_oauth.get("client_secret")
                            
                            gcp_secrets = {
                                "installed": {
                                    "client_id": client_id,
                                    "client_secret": client_secret,
                                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                                    "token_uri": "https://oauth2.googleapis.com/token",
                                    "redirect_uris": ["http://localhost"]
                                }
                            }
                            with open(cred_path, "w") as f:
                                json.dump(gcp_secrets, f)
                            logger.info(f"📄 Wrote {name} client secrets to {cred_path}")
                        
                        # 2. Write Token File (The actual OAuth tokens)
                        token_json = {
                            "access_token": token_data["access_token"],
                            "refresh_token": token_data.get("refresh_token"),
                            "scope": " ".join(token_data.get("scopes", [])),
                            "token_type": "Bearer",
                            "expiry_date": expiry_date
                        }
                        
                        # Some servers expect 'token.json' (Gmail) others 'tokens.json' (GDrive)
                        # We write both to be safe or specific ones based on service
                        with open(tokens_path, "w") as f:
                            json.dump(token_json, f)
                        
                        # Set redundant files for maximum compatibility
                        cred_file_path = cred_dir / "credentials.json"
                        token_file_path = cred_dir / "tokens.json"
                        
                        # Also write token.json (singular) for Gmail compatibility
                        token_singular_path = cred_dir / "token.json"
                        with open(token_singular_path, "w") as f:
                            json.dump(token_json, f)

                        # 3. Inject Environment Variables based on what the specific MCP server expects
                        if "env" not in resolved_config:
                            resolved_config["env"] = {}
                        
                        if name == "google-drive":
                            # @piotr-agier/google-drive-mcp
                            resolved_config["env"]["GOOGLE_DRIVE_OAUTH_CREDENTIALS"] = str(cred_path)
                            resolved_config["env"]["GOOGLE_DRIVE_MCP_TOKEN_PATH"] = str(tokens_path)
                        elif name == "google-calendar":
                            # @cocal/google-calendar-mcp
                            resolved_config["env"]["GOOGLE_OAUTH_CREDENTIALS"] = str(cred_path)
                            resolved_config["env"]["GOOGLE_CALENDAR_MCP_TOKEN_PATH"] = str(tokens_path)
                        elif name == "gmail-mcp":
                            # Support multiple server variants (LobeHub, Gongrzhe, Official)
                            # Gongrzhe variant (@gongrzhe/server-gmail-autoauth-mcp)
                            resolved_config["env"]["GMAIL_OAUTH_PATH"] = str(cred_path)
                            resolved_config["env"]["GMAIL_CREDENTIALS_PATH"] = str(token_singular_path)
                            # LobeHub / Official-like variants
                            resolved_config["env"]["GMAIL_CREDENTIALS_FILE"] = str(cred_path)
                            resolved_config["env"]["GMAIL_TOKEN_FILE"] = str(token_singular_path)
                            # Generic / Legacy
                            resolved_config["env"]["GMAIL_CONFIG_PATH"] = str(cred_dir)
                            
                        logger.info(f"📄 Prepared EPHEMERAL {name} credentials in {cred_dir}")
                        logger.info(f"   These files will be DELETED after connection")
                        
                        # Mark these as ephemeral files to be deleted after connection
                        resolved_config["_temp_cred_path"] = str(cred_path)
                        resolved_config["_temp_token_path"] = str(tokens_path)
                        resolved_config["_temp_token_singular_path"] = str(token_singular_path)
                        resolved_config["_temp_dir"] = str(cred_dir)
                        resolved_config["_is_google_service"] = True  # Flag for aggressive cleanup
                        
                    except Exception as e:
                        logger.error(f"Failed to prepare {name} credentials: {e}")
                        raise Exception(f"Failed to prepare {name} credentials: {e}")
                else:
                    logger.warning(f"⚠️  No {name} tokens found in database")
                    raise Exception(f"{name} not authenticated. Please click 'Connect Tools' to authenticate first.")
            
            # 2. Inject OAuth tokens for all other OAuth services (GitHub, Zoho, etc.)
            if not is_google_service:
                # Check for Registration Data (DCR) regardless of is_oauth_server status
                # (Atlassian/Zoho might count as oauth_server or not depending on config, but they need registration)
                try:
                    reg_service_name = f"{name}:registration"
                    reg_token_data = await self.token_manager.get_token(reg_service_name)
                    
                    if reg_token_data and reg_token_data.get("access_token"):
                        logger.info(f"🔍 Found stored registration data for {name}")
                        import json
                        from urllib.parse import urlparse
                        
                        reg_content = json.loads(reg_token_data["access_token"])
                        
                        # CRITICAL: If we have registration data, we SHOULD have client_id/client_secret.
                        # Injecting these into the config can help mcp-use skip re-registration.
                        if "client_id" in reg_content and "client_secret" in reg_content:
                            if "auth" not in resolved_config:
                                resolved_config["auth"] = {
                                    "client_id": reg_content["client_id"],
                                    "client_secret": reg_content["client_secret"]
                                }
                                logger.info(f"   Injected captured DCR credentials into 'auth' block")
                        
                        mcp_use_reg_dir = Path.home() / ".mcp_use" / "tokens" / "registrations"
                        mcp_use_reg_dir.mkdir(parents=True, exist_ok=True)
                        mcp_use_token_dir = Path.home() / ".mcp_use" / "tokens"
                        
                        # We need to reconstruct the filename mcp-use expects.
                        server_url = resolved_config.get("url")
                        restored_files = []
                        
                        if server_url:
                            try:
                                # Try multiple variants of URL-based names
                                no_proto = server_url.replace("https://", "").replace("http://", "")
                                if "?" in no_proto: no_proto = no_proto.split("?")[0]
                                
                                # Filename candidates
                                candidates = []
                                candidates.append(f"{no_proto.replace('/', '__')}_registration.json")
                                candidates.append(f"{no_proto.replace('/', '_')}_registration.json") 
                                
                                # Also handle netloc + sanitized path
                                parsed = urlparse(server_url)
                                candidates.append(f"{parsed.netloc}_{parsed.path.replace('/', '_')}_registration.json")
                                candidates.append(f"{parsed.netloc}__{parsed.path.replace('/', '_')}_registration.json")
                                
                                # Clean up duplicates and empty strings
                                candidates = list(set([c for c in candidates if c]))
                                
                                # Write to both registrations subdir AND main tokens dir
                                for fname in candidates:
                                    # Target 1: registrations/
                                    fpath1 = mcp_use_reg_dir / fname
                                    with open(fpath1, "w") as f:
                                        json.dump(reg_content, f)
                                    restored_files.append(f"registrations/{fname}")
                                    
                                    # Target 2: tokens/ (some versions use this)
                                    fpath2 = mcp_use_token_dir / fname
                                    with open(fpath2, "w") as f:
                                        json.dump(reg_content, f)
                                    restored_files.append(f"tokens/{fname}")
                                    
                            except Exception as e:
                                logger.warning(f"Failed to generate registration filename from URL: {e}")
                        
                        # Fallback: user-specific name
                        fname = f"{name}_{self.user_id}_registration.json"
                        fpath = mcp_use_reg_dir / fname
                        with open(fpath, "w") as f:
                            json.dump(reg_content, f)
                        restored_files.append(fname)
                            
                        logger.info(f"   📄 Restored registration files: {len(restored_files)} variants")
                except Exception as e:
                    logger.warning(f"Failed to restore registration data for {name}: {e}")

            if not is_google_service and is_oauth_server:
                logger.info(f"🔍 OAuth server detected ({name}) for user_id={self.user_id}")
                token_data = await self.token_manager.get_token(name)
                
                if token_data:
                     logger.info(f"   ✅ [Manager] Found stored token for {name}: {list(token_data.keys())}")
                else:
                     logger.info(f"   ⚠️ [Manager] No stored token found for {name}")
                
                mcp_use_token_dir = Path.home() / ".mcp_use" / "tokens"
                mcp_use_token_dir.mkdir(parents=True, exist_ok=True)
                target_token_file = mcp_use_token_dir / f"{mcp_use_name}.json"
                
                # IMPORTANT: mcp-use for httpx servers REQUIRES 'auth' field in config during create_session
                # even if we provide the token file manually.
                if "custom_oauth" in resolved_config:
                    co = resolved_config["custom_oauth"]
                    if "auth" not in resolved_config:
                        resolved_config["auth"] = {
                            "client_id": co.get("client_id"),
                            "client_secret": co.get("client_secret")
                        }
                        logger.info(f"   Injected 'auth' block into config using 'custom_oauth' credentials")

                if token_data and token_data.get("access_token"):
                    logger.info(f"✅ Found {name} token in database for user_id={self.user_id}")
                    logger.info(f"📄 Creating ephemeral token file: {target_token_file}")
                    
                    # Calculate expiry string if needed
                    # Calculate expiry string if needed
                    expires_at_str = token_data.get("expires_at")
                    if not expires_at_str:
                        if token_data.get("expires_in"):
                            from datetime import timezone
                            dt = datetime.now(timezone.utc) + timedelta(seconds=token_data.get("expires_in"))
                            expires_at_str = dt.isoformat().replace("+00:00", "Z")
                        else:
                            # Fallback for non-expiring tokens (like GitHub PATs sometimes)
                            # Set to 1 year in future to prevent immediate re-auth
                            from datetime import timezone
                            dt = datetime.now(timezone.utc) + timedelta(days=365)
                            expires_at_str = dt.isoformat().replace("+00:00", "Z")
                            logger.info(f"   ℹ️  No expiry found for {name}, defaulting to 1 year future: {expires_at_str}")

                    reconstructed_token = {
                        "access_token": token_data.get("access_token"),
                        "refresh_token": token_data.get("refresh_token"),
                        "scope": " ".join(token_data.get("scopes", [])) if isinstance(token_data.get("scopes"), list) else token_data.get("scopes", ""),
                        "token_type": "Bearer", 
                        "expires_at": expires_at_str
                    }
                    
                    import json
                    from urllib.parse import urlparse
                    
                    try:
                        # CRITICAL: Only create user-specific token file for proper isolation
                        # DO NOT create URL-based files as they are shared across users
                        with open(target_token_file, "w") as f:
                            json.dump(reconstructed_token, f)
                        
                        logger.info(f"   ✅ Created user-specific token file: {target_token_file.name}")
                        logger.info(f"   🔒 User isolation ensured - only {self.user_id} can use this token")
                    except Exception as e:
                        logger.error(f"Failed to write ephemeral token: {e}")
                else:
                    # If it's an httpx OAuth server but we have no token, we can't connect
                    # If it's an httpx OAuth server but we have no token, check if we can rely on local state
                    if resolved_config.get("type") == "httpx":
                        # Check if we should allow proceed without DB token
                        can_proceed = False

                        # Case 1: PKCE enabled (Likely handling its own auth locally first)
                        if resolved_config.get("use_pkce"):
                            can_proceed = True
                            logger.info(f"ℹ️  {name} uses PKCE - proceeding without initial DB token (will capture later)")

                        # Case 2: Local token file already exists (from previous run)
                        elif target_token_file.exists():
                            can_proceed = True
                            logger.info(f"ℹ️  Found existing local token for {name} - proceeding without DB token")
                        
                        # Case 3: We have a token in DB (captured above), inject it into headers
                        elif token_data and token_data.get("access_token"):
                            # This is key for GitHub: we must inject the header manually because
                            # mcp-use might not pick up the file correctly for httpx transport
                            # or we just want to be explicit.
                            if "headers" not in resolved_config:
                                resolved_config["headers"] = {}
                            
                            # Inject Authorization header
                            resolved_config["headers"]["Authorization"] = f"Bearer {token_data['access_token']}"
                            can_proceed = True
                            logger.info(f"💉 Injected Authorization header for {name} from DB token")

                        if not can_proceed:
                            logger.warning(f"⚠️  No {name} tokens found in database for httpx server")
                            raise Exception(f"{name} not authenticated. Please click 'Connect Tools' to authenticate first.")
                    
                    # For other types, we might just want to ensure no stale file block
                    # ONLY delete if we didn't just decide to use it
                    if target_token_file.exists() and not can_proceed:
                        try:
                            target_token_file.unlink()
                            logger.info(f"🧹 Removed stale token file {target_token_file} to force auth")
                        except Exception as e:
                            logger.error(f"Failed to remove stale token: {e}")
            
            
            # Windows fix
            if os.name == 'nt' and resolved_config.get("command") == "npx":
                resolved_config["command"] = "npx.cmd"
 
            # CRITICAL: Strip OAuth config fields before passing to mcp-use.
            # This prevents mcp-use from launching its own internal OAuth flow (the second auth screen).
            if "custom_oauth" in resolved_config:
                del resolved_config["custom_oauth"]
            if "use_pkce" in resolved_config:
                del resolved_config["use_pkce"]

            # mcp-use: Register then Connect
            logger.info(f"🔌 Connecting to MCP server: {name} (as {mcp_use_name})")
            self._client.add_server(mcp_use_name, resolved_config)
            self._sessions[mcp_use_name] = await self._client.create_session(mcp_use_name)
            
            logger.info(f"✅ Connected: {name} (session: {mcp_use_name})")
            
            # CRITICAL: For OAuth servers, capture token BEFORE cleanup
            # The token file must exist for capture to work
            if is_oauth_server:
                logger.info(f"📥 Attempting to capture OAuth token for {name}")
                await self._capture_and_store_oauth_token(name)
            
            # SAFETY CHECK: Only delete tokens if we are sure they are in the database (or if not OAuth)
            # This prevents losing the local token file if DB capture failed for a PKCE flow
            should_cleanup = True
            if is_oauth_server:
                 # Check if we have the token in DB now
                 stored_token = await self.token_manager.get_token(name)
                 if not stored_token or not stored_token.get("access_token"):
                     should_cleanup = False
                     logger.warning(f"⚠️  Token for {name} NOT confirmed in database - skipping aggressive file cleanup to preserve session keys")
            
            # CRITICAL: Delete ALL token files immediately after token capture (if safe)
            # This handles both user-specific naming AND URL-based naming from mcp-use
            # (e.g., api.githubcopilot.com__mcp.json for httpx servers)
            if should_cleanup:
                try:
                    mcp_use_token_dir = Path.home() / ".mcp_use" / "tokens"
                    if mcp_use_token_dir.exists():
                        deleted_files = []
                        for token_file in mcp_use_token_dir.glob("*.json"):
                            try:
                                token_file.unlink()
                                deleted_files.append(token_file.name)
                            except Exception as e:
                                logger.warning(f"Failed to delete {token_file.name}: {e}")
                        
                        if deleted_files:
                            logger.info(f"🗑️  Deleted {len(deleted_files)} ephemeral token file(s): {', '.join(deleted_files)}")
                    
                    # Also cleanup registrations folder
                    # CRITICAL FIX: Delete registrations because we are now capturing them into DB
                    mcp_use_reg_dir = Path.home() / ".mcp_use" / "tokens" / "registrations"
                    if mcp_use_reg_dir.exists():
                        deleted_regs = []
                        for reg_file in mcp_use_reg_dir.glob("*.json"):
                             try:
                                reg_file.unlink()
                                deleted_regs.append(reg_file.name)
                             except Exception as e:
                                logger.warning(f"Failed to delete registration {reg_file.name}: {e}")
                        if deleted_regs:
                            logger.info(f"🗑️  Deleted {len(deleted_regs)} registration file(s) (captured in DB)")
                except Exception as e:
                    logger.warning(f"Failed to cleanup token files: {e}")

            
            # CRITICAL: Delete Google service credential directories immediately
            # Gmail, Google Drive, Google Calendar credentials should NOT persist locally
            if resolved_config.get("_is_google_service"):
                try:
                    temp_dir = resolved_config.get("_temp_dir")
                    if temp_dir:
                        temp_dir_path = Path(temp_dir)
                        if temp_dir_path.exists():
                            import shutil
                            shutil.rmtree(temp_dir_path)
                            logger.info(f"🗑️  Deleted ephemeral Google service directory: {temp_dir_path}")
                            
                            # Also delete parent user directory if it's now empty
                            parent_dir = temp_dir_path.parent  # e.g., ~/.sphere/mcp_data/{user_id}/
                            if parent_dir.exists() and parent_dir.is_dir():
                                try:
                                    # Check if directory is empty
                                    if not any(parent_dir.iterdir()):
                                        parent_dir.rmdir()
                                        logger.info(f"🗑️  Deleted empty user directory: {parent_dir}")
                                except Exception:
                                    pass  # Directory not empty, keep it

                            logger.info(f"   Database is the ONLY token storage for {name}")
                except Exception as e:
                    logger.warning(f"Failed to delete Google service directory: {e}")
            
            logger.info(f"   ✅ Database is now the only token storage")
  
            # CLEANUP: Delete temporary credentials files
            cleanup_keys = ["_temp_cred_path", "_temp_token_path", "_temp_token_path_alt"]
            
            async def delayed_cleanup():
                await asyncio.sleep(5) # Wait for server to fully initialize
                for key in cleanup_keys:
                    p_str = resolved_config.get(key)
                    if p_str:
                        p = Path(p_str)
                        if p.exists():
                            try:
                                p.unlink()
                                logger.info(f"🧹 Cleaned up temporary file: {p}")
                            except Exception as e:
                                logger.warning(f"Failed to cleanup {p}: {e}")
                
                # Finally, try to remove the directory if it's empty
                dir_path_str = resolved_config.get("_temp_dir")
                if dir_path_str:
                    dir_path = Path(dir_path_str)
                    if dir_path.exists() and dir_path.is_dir():
                        try:
                            # Only remove if it's empty (or only contains hidden files we don't care about?)
                            # For now, rm if empty
                            dir_path.rmdir()
                            logger.info(f"🧹 Cleaned up empty directory: {dir_path}")
                        except Exception:
                            # If not empty (e.g. other files generated by server), leave it
                            pass
            
            # Start cleanup in background
            asyncio.create_task(delayed_cleanup())
                
        except Exception as e:
            logger.error(f"❌ Connection failed for {name}: {e}")
            raise e

    async def _capture_and_store_oauth_token(self, service_name: str):
        """
        Capture OAuth token from mcp-use storage and persist to database.
        
        After storing in database, deletes the mcp-use token file to force
        all future connections to use database tokens exclusively.
        """
        try:
            import json
            from pathlib import Path
            
            logger.info(f"🔍 Starting token capture for {service_name}")
            
            # mcp-use stores tokens in ~/.mcp_use/tokens/
            mcp_use_token_dir = Path.home() / ".mcp_use" / "tokens"
            
            if not mcp_use_token_dir.exists():
                logger.warning(f"❌ Token directory {mcp_use_token_dir} does not exist")
                logger.warning(f"   OAuth flow may not have completed")
                return
            
            # Retry loop to wait for token file to appear (async IO race condition handling)
            import asyncio
            token_file = None
            max_retries = 30  # Increased retries
            retry_delay = 2.0  # Increased delay (Total ~60s)
            
            # Multi-user isolation: look for the user-specific file name
            mcp_use_name = f"{service_name}_{self.user_id}"
            target_filename = f"{mcp_use_name}.json"
            
            for attempt in range(max_retries):
                token_files = []
                
                # 1. Check standard mcp-use locations with user-isolated filename
                if mcp_use_token_dir.exists():
                    token_files.extend(list(mcp_use_token_dir.glob(target_filename)))
                
                # 2. ALSO check for URL-based filenames (e.g., api.githubcopilot.com__mcp.json)
                import time
                current_time = time.time()
                if mcp_use_token_dir.exists():
                    for json_file in mcp_use_token_dir.glob("*.json"):
                        # Check if file was modified recently (within last 10 seconds)
                        if current_time - json_file.stat().st_mtime < 10:
                            if json_file not in token_files:
                                token_files.append(json_file)
                
                # 3. Check for newly introduced isolated directories for Google services
                google_isolated_dir = Path.home() / ".sphere" / "mcp_data" / str(self.user_id) / service_name
                google_extra_files = ["token.json", "tokens.json"]
                
                for extra_file in google_extra_files:
                    path = google_isolated_dir / extra_file
                    if path.exists():
                         token_files.append(path)
                
                # 4. Legacy Gmail MCP specific location
                gmail_dir = Path.home() / ".gmail-mcp"
                potential_files = ["token.json", "credentials.json"]
                
                for potential_file in potential_files:
                    path = gmail_dir / potential_file
                    if path.exists():
                         token_files.append(path)
                
                if token_files:
                    # Get the most recently modified file
                    newest_file = max(token_files, key=lambda p: p.stat().st_mtime)
                    
                    # Check if this file is recent (modified in the last minute)
                    if current_time - newest_file.stat().st_mtime < 60:
                        token_file = newest_file
                        break
                
                if token_file:
                    break
                    
                await asyncio.sleep(retry_delay)
            
            # Additional check for Registration files (DCR - Dynamic Client Registration)
            # Some services like Zoho/Atlassian create a registration file that is needed for subsequent connections
            # We want to capture this too.
            registration_files = []
            mcp_use_reg_dir = Path.home() / ".mcp_use" / "tokens" / "registrations"
            
            # 1. Check in registrations subdir
            if mcp_use_reg_dir.exists():
                for reg_file in mcp_use_reg_dir.glob("*.json"):
                    if current_time - reg_file.stat().st_mtime < 120: # slightly longer window for registration
                         registration_files.append(reg_file)

            # 2. Check in main tokens dir (sometimes they end up here depending on mcp-use version/config)
            for reg_file in mcp_use_token_dir.glob("*registration.json"):
                 if current_time - reg_file.stat().st_mtime < 120:
                     if reg_file not in registration_files:
                         registration_files.append(reg_file)

            # Process Registration Files
            if registration_files:
                 logger.info(f"🔍 Found {len(registration_files)} potential registration files")
                 # We want to find the one relevant to our service. 
                 # Heuristic: check if filename contains service name or parts of the URL
                 
                 for reg_file in registration_files:
                     if service_name in reg_file.name or service_name.replace("-", "") in reg_file.name:
                         logger.info(f"   Capturing registration file: {reg_file.name}")
                         try:
                             with open(reg_file, "r") as f:
                                 reg_content = json.load(f)
                             
                             # Store as a special "token" in DB with :registration suffix
                             # We use the access_token field to store the whole JSON content stringified
                             reg_service_name = f"{service_name}:registration"
                             
                             await self.token_manager.store_token(
                                 service=reg_service_name,
                                 access_token=json.dumps(reg_content), # Store full JSON in access_token field
                                 refresh_token=None,
                                 token_uri=None,
                                 scopes=["registration"],
                                 expires_in=315360000 # 10 years (effectively permanent)
                             )
                             logger.info(f"   ✅ Stored registration in DB for {reg_service_name}")
                             
                             # Delete payload
                             try:
                                 reg_file.unlink()
                                 logger.info(f"   Deleted local registration file: {reg_file.name}")
                             except Exception as exc:
                                 logger.warning(f"   Failed to delete registration file: {exc}")
                                 
                         except Exception as e:
                             logger.error(f"   Failed to capture registration {reg_file}: {e}")

            if not token_file:
                logger.warning(f"❌ Timed out waiting for token file for {service_name}")
                return

            logger.info(f"✅ Found token file: {token_file}")
            
            with open(token_file, "r") as f:
                data = json.load(f)
                
            # Extract fields with variants
            access_token = data.get("access_token") or data.get("accessToken")
            refresh_token = data.get("refresh_token") or data.get("refreshToken")
            
            # Handle scopes as list or space-separated string
            scopes_raw = data.get("scope") or data.get("scopes") or []
            if isinstance(scopes_raw, str):
                scopes = scopes_raw.split(" ")
            else:
                scopes = scopes_raw
            
            # Calculate expiry
            expires_in = data.get("expires_in") or data.get("expiresIn")
            
            # Check for expiry_date (timestamp in ms) - used by Google
            if not expires_in and data.get("expiry_date"):
                # Convert to seconds from now
                exp_ms = data.get("expiry_date")
                exp_sec = exp_ms / 1000
                now_sec = datetime.now().timestamp()
                expires_in = int(exp_sec - now_sec)
                if expires_in < 0: expires_in = 0
            
            if access_token:
                await self.token_manager.store_token(
                    service=service_name,
                    access_token=access_token,
                    refresh_token=refresh_token,
                    token_uri=None, # We don't always get this from the file
                    scopes=scopes,
                    expires_in=expires_in
                )
                logger.info(f"✅ Captured and stored tokens for {service_name}")
                if not refresh_token:
                     logger.warning(f"⚠️  No refresh_token found for {service_name} - persistence may be limited to session duration")
            else:
                logger.warning(f"⚠️  Token file found but contained no access_token. Keys: {list(data.keys())}")
                
        except Exception as e:
            logger.error(f"Failed to capture/store token for {service_name}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            
    async def disconnect_server(self, name: str):
        """Disconnect active session."""
        mcp_use_name = f"{name}_{self.user_id}"
        if mcp_use_name in self._sessions:
            self._sessions.pop(mcp_use_name, None)
            
        # Clear tool cache
        if name in self._tools_cache:
            del self._tools_cache[name]

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
            mcp_use_name = f"{name}_{self.user_id}"
            if config and config.get("enabled", True) and mcp_use_name not in self._sessions:
                try:
                    await self._connect_single(name, config)
                except Exception as e:
                    logger.error(f"Failed to connect to {name} during get_tools: {e}")

        for name, config in self._server_configs.items():
            # If explicit list provided, skip others
            if server_names and name not in server_names:
                continue
            
            mcp_use_name = f"{name}_{self.user_id}"
            session = self._sessions.get(mcp_use_name)
            if not session:
                continue

            disabled_tools = config.get("disabled_tools", [])
            
            try:
                # Use standard adapter logic
                tools = await self._fetch_tools_from_session(name, session)
                
                for tool in tools:
                    if tool.name in disabled_tools:
                        continue
                    
                    # Fix output types (common issue with some tools)
                    tool = self._ensure_string_output(tool)
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

    async def get_all_tools_status(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Get flattened status of all tools for UI."""
        status = {}
        import time
        
        sensitive_patterns = self._hitl_config.get("sensitive_tools", [])
        
        for name, config in self._server_configs.items():
            is_enabled = config.get("enabled", True)
            mcp_use_name = f"{name}_{self.user_id}"
            connected = mcp_use_name in self._sessions
            
            server_tools = []
            
            try:
                if connected:
                    # Check cache first
                    cache_entry = self._tools_cache.get(name)
                    now = time.time()
                    
                    if not force_refresh and cache_entry and (now - cache_entry["timestamp"] < self._CACHE_TTL):
                        raw_tools = cache_entry["tools"]
                        logger.debug(f"🔦 Using cached tools for {name}")
                    else:
                        logger.info(f"🔄 Refreshing tools for {name} (forced={force_refresh})")
                        result = await self._sessions[mcp_use_name].list_tools()
                        # Robust handle: result might be a list or an object with .tools
                        if hasattr(result, 'tools'):
                            raw_tools = result.tools
                        elif isinstance(result, list):
                            raw_tools = result
                        else:
                            logger.warning(f"Unexpected tools format from {name}: {type(result)}")
                            raw_tools = []
                        
                        # Update cache
                        self._tools_cache[name] = {
                            "tools": raw_tools,
                            "timestamp": now
                        }

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

    def _ensure_string_output(self, tool: StructuredTool) -> StructuredTool:
        """Wraps tool to force string output (fixes 422 validation errors)."""
        original_func = tool.coroutine
        
        async def wrapper(**kwargs):
            # Fix specific tool quirks here if needed
            if "firecrawl" in tool.name and "sources" in kwargs:
                 kwargs["sources"] = [{"type": s} if isinstance(s, str) else s for s in kwargs["sources"]]
            
            result = await original_func(**kwargs)
            
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
