import os
import asyncio
import logging
import json
from typing import Dict, List, Any, Optional
import fnmatch

# Import mcp-use components
from mcp_use.client import MCPClient
from langchain_core.tools import StructuredTool
from langgraph.types import interrupt

# Import langchain-mcp-adapters for tool conversion
from langchain_mcp_adapters.tools import load_mcp_tools

class ApprovalRequiredError(Exception):
    """Raised when a tool call requires human approval."""
    def __init__(self, tool_name: str, tool_args: Dict[str, Any], message: str):
        self.tool_name = tool_name
        self.tool_args = tool_args
        self.message = message
        super().__init__(self.message)

# Import mcp-use middleware components
from mcp_use.client.middleware.middleware import Middleware, MiddlewareContext


from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.config.database import async_engine
from src.core.state.models import User, MCPServerConfig
from src.core.auth.security import encrypt_value, decrypt_value
from src.core.mcp.registry import SPHERE_REGISTRY, get_app_by_id

logger = logging.getLogger(__name__)

class ApprovalMiddleware(Middleware):
    """Middleware to intercept sensitive tool calls and request approval."""
    def __init__(self, manager: 'MCPManager'):
        self.manager = manager

    async def process_request(self, context: MiddlewareContext):
        # DEBUG: Trace request
        # print(f"DEBUG: Middleware request: {context.request_type}")
        if context.request_type == "call_tool":
            tool_name = context.params.get("name")
            tool_args = context.params.get("arguments", {})
            print(f"DEBUG: HITL Middleware checking tool: {tool_name}")
            
            # Check if this tool needs approval
            hitl_config = self.manager.config_data.get("hitl_config", {})
            if hitl_config.get("enabled", False):
                mode = hitl_config.get("mode", "denylist")
                sensitive_tools = hitl_config.get("sensitive_tools", [])
                
                # print(f"DEBUG: HITL mode={mode}, sensitive_tools={sensitive_tools}")
                
                requires_approval = False
                if mode == "allowlist":
                    requires_approval = True
                elif mode == "denylist":
                    # Extract base name for global matching
                    base_name = tool_name.split("__")[-1] if "__" in tool_name else tool_name
                    
                    for pattern in sensitive_tools:
                        # Match against either full namespaced name OR the base name
                        if fnmatch.fnmatch(tool_name, pattern) or fnmatch.fnmatch(base_name, pattern):
                            requires_approval = True
                            logger.info(f"HITL Match: Tool {tool_name} (base: {base_name}) matched pattern {pattern}")
                            break
                
                # Check whitelist (bypass HITL if tool_name in whitelisted_tools)
                if tool_name in self.manager.whitelisted_tools:
                    print(f"DEBUG: Tool {tool_name} is in whitelist. Bypassing HITL.")
                    requires_approval = False

                if requires_approval:
                    logger.info(f"🛑 HITL Approval Required via Middleware: {tool_name}")
                    raise ApprovalRequiredError(
                        tool_name=tool_name,
                        tool_args=tool_args,
                        message=hitl_config.get("approval_message", "Approve execution?")
                    )
        
        return await context.next()

class MCPManager:
    """
    Universal MCP Manager using mcp-use library.
    Orchestrates all MCP servers, handles configuration, and manages tools.
    Now supporting Multi-User DB storage.
    """
    
    def __init__(self, user_id: Any):
        self.user_id = user_id
        
        # Central MCPClient to manage all servers
        self._mcp_client: Optional[MCPClient] = None
        
        # Map server_name -> MCPSession
        self.server_sessions: Dict[str, Any] = {}
        
        # Default global config (hitl, etc.)
        self.config_data = {
            "mcpServers": {}, 
            "hitl_config": {
                "enabled": True, 
                "mode": "denylist", 
                "sensitive_tools": ["*google*", "*delete*", "*remove*", "*write*", "*-rm"]
            }
        }
        # Runtime cache for session-approved tools
        self.whitelisted_tools: set[str] = set()
        
        # Tool Definition Cache (server_name -> list[tool])
        self.tool_cache: Dict[str, List[Any]] = {}

    def whitelist_tool(self, tool_name: str, tool_args: dict):
        """Add a tool + args signature to the session whitelist to bypass HITL."""
        sig = self._compute_signature(tool_name, tool_args)
        self.whitelisted_tools.add(sig)
        logger.info(f"Tool {tool_name} whitelisted for this session.")
        
    async def _load_config_from_db(self):
        """Load configuration from DB for the current user."""
        async with AsyncSession(async_engine) as session:
            # 1. Load User Settings (HITL Config)
            user_stmt = select(User).where(User.id == self.user_id)
            user_result = await session.execute(user_stmt)
            user = user_result.scalar_one_or_none()
            if user and user.hitl_config:
                self.config_data["hitl_config"] = user.hitl_config
                logger.info(f"Loaded HITL config for user {self.user_id}.")

            # 2. Load MCP Servers
            stmt = select(MCPServerConfig).where(MCPServerConfig.user_id == self.user_id)
            result = await session.execute(stmt)
            configs = result.scalars().all()
            
            mcp_servers = {}
            for row in configs:
                config = row.config
                if row.is_encrypted:
                    config = self._decrypt_config(config)
                
                # Ensure 'enabled' flag is preserved in runtime config
                config["enabled"] = row.enabled
                mcp_servers[row.name] = config
                
            self.config_data["mcpServers"] = mcp_servers
            return self.config_data

    async def update_user_hitl_config(self, hitl_config: Dict[str, Any]):
        """Update user's HITL settings in the database."""
        async with AsyncSession(async_engine) as session:
            stmt = select(User).where(User.id == self.user_id)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()
            
            if user:
                # Merge or replace? For now, replace.
                user.hitl_config = hitl_config
                await session.commit()
                # Refresh runtime cache
                self.config_data["hitl_config"] = hitl_config
                logger.info(f"Updated HITL config for user {self.user_id}.")
                return True
            return False

    async def _save_config_to_db(self, server_name: str, config: Dict[str, Any]):
        """Save/Update configuration in DB for the current user."""
        async with AsyncSession(async_engine) as session:
            # Check if exists
            stmt = select(MCPServerConfig).where(
                MCPServerConfig.user_id == self.user_id,
                MCPServerConfig.name == server_name
            )
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            
            enabled = config.pop("enabled", True)
            
            # Encrypt sensitive parts before saving
            encrypted_config = self._encrypt_config(config)
            
            if row:
                row.config = encrypted_config
                row.enabled = enabled
                row.is_encrypted = True
            else:
                row = MCPServerConfig(
                    user_id=self.user_id,
                    name=server_name,
                    config=encrypted_config,
                    enabled=enabled,
                    is_encrypted=True
                )
                session.add(row)
                
            await session.commit()
            # Refresh runtime cache
            await self._load_config_from_db()

    def _encrypt_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Encrypt sensitive env vars in config."""
        import copy
        c = copy.deepcopy(config)
        if "env" in c:
            for k, v in c["env"].items():
                if "TOKEN" in k.upper() or "KEY" in k.upper() or "SECRET" in k.upper():
                    c["env"][k] = encrypt_value(v)
        return c

    def _decrypt_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Decrypt sensitive env vars in config."""
        import copy
        c = copy.deepcopy(config)
        if "env" in c:
            for k, v in c["env"].items():
                if "TOKEN" in k.upper() or "KEY" in k.upper() or "SECRET" in k.upper():
                    c["env"][k] = decrypt_value(v)
        return c
            
    async def initialize(self):
        """
        Instant initialization. 
        Just prepares the client and loads config, doesn't connect yet.
        """
        logger.info(f"Initializing MCP Manager (User: {self.user_id})...")
        
        # Reset state to ensure fresh loop binding
        if self._mcp_client:
            try:
                await self._mcp_client.close_all_sessions()
            except: pass
            
        await self._load_config_from_db()
        self.server_sessions = {} # Clear old sessions bound to old loops
        self.tool_cache = {}
        
        # Initialize client with ApprovalMiddleware
        self._mcp_client = MCPClient(
            middleware=[ApprovalMiddleware(self)]
        )
        # No server initialization here for instant startup

    async def connect_to_servers(self, server_names: List[str]):
        """
        Connect to specific servers if not already connected.
        Implementation of the 'Plan-first, Connect-later' pattern.
        """
        if not self._mcp_client:
            self._mcp_client = MCPClient(
                middleware=[ApprovalMiddleware(self)]
            )
            
        mcp_servers = self.config_data.get("mcpServers", {})
        init_tasks = []
        
        for name in server_names:
            if name in self.server_sessions:
                continue
            
            config = mcp_servers.get(name)
            if not config:
                logger.warning(f"Server {name} not found in config.")
                continue
            
            # CHECK ENABLED STATUS
            if not config.get("enabled", True):
                # Optionally log, but usually silent is fine or info
                logger.info(f"Skipping disabled server: {name}")
                continue

            init_tasks.append(self.init_server(name, config))
            
        if init_tasks:
            logger.info(f"🔌 Connecting to servers: {', '.join(server_names)}")
            await asyncio.gather(*init_tasks, return_exceptions=True)

    def _resolve_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve environment variables in configuration."""
        import copy
        resolved = copy.deepcopy(config)
        
        # Resolve 'env' dictionary
        if "env" in resolved:
            env = resolved["env"]
            for k, v in env.items():
                if isinstance(v, str) and v.startswith("${") and v.endswith("}"):
                    var_name = v[2:-1]
                    val = os.getenv(var_name)
                    if val:
                        env[k] = val
            resolved["env"] = env
            
        return resolved

    async def init_server(self, name: str, config: Dict[str, Any]):
        """Initialize a single MCP server using mcp-use."""
        try:
            # Resolve configuration
            server_config = self._resolve_config(config)

            # Windows compatibility for npx
            if os.name == 'nt' and server_config.get("command") == "npx":
                server_config["command"] = "npx.cmd"
            
            self._mcp_client.add_server(name, server_config)
            session = await self._mcp_client.create_session(name)
            
            self.server_sessions[name] = session
            logger.info(f"✅ Connected to server: {name}")
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ Failed to connect to server {name}: {error_msg}")
            # If it's a common npm error on Windows, provide a hint
            if "Connection closed" in error_msg or "npx" in error_msg:
                logger.warning("💡 Hint: If using npx on Windows, ensure npx is working and you aren't hit by 'npm notice Access token expired'. Try running 'npm logout' in your terminal.")

    async def cleanup(self):
        """Disconnect all servers."""
        if self._mcp_client:
            try:
                await self._mcp_client.close_all_sessions()
            except Exception:
                pass
            self._mcp_client = None
        self.server_sessions.clear()

    async def get_tools_for_servers(self, server_names: List[str]) -> List[StructuredTool]:
        """Connect to servers and get tools using langchain-mcp-adapters."""
        # Ensure targeted servers are connected (this will now skip disabled ones)
        await self.connect_to_servers(server_names)
        
        all_tools = []
        used_names = set()
        
        for name in server_names:
            # Double check config in case it was connected previously but now disabled
            mcp_servers = self.config_data.get("mcpServers", {})
            server_cfg = mcp_servers.get(name, {})
            if not server_cfg.get("enabled", True):
                continue

            session = self.server_sessions.get(name)
            if not session:
                continue
                
            try:
                # Adapter and load_mcp_tools logic (unchanged)
                class ListToolsResult:
                    def __init__(self, tools):
                        self.tools = tools
                        self.nextCursor = None

                class SessionAdapter:
                    def __init__(self, sess):
                        self.sess = sess
                    async def list_tools(self, cursor: str = None):
                        tools = await self.sess.list_tools()
                        return ListToolsResult(tools)
                    async def call_tool(self, name: str, arguments: dict, **kwargs):
                        return await self.sess.call_tool(name=name, arguments=arguments)

                adapter = SessionAdapter(session)
                mcp_tools = await load_mcp_tools(adapter)
                
                server_config = mcp_servers.get(name, {})
                disabled_tools = server_config.get("disabled_tools", [])
                
                for tool in mcp_tools:
                    if tool.name in disabled_tools:
                        continue
                    
                    # Logic for Smart Namespacing
                    original_name = tool.name
                    if original_name in used_names:
                        # Collision! Prefix with server name
                        safe_server_name = name.replace("-", "_").replace(".", "_").replace(" ", "_").lower()
                        effective_name = f"{safe_server_name}_{original_name}"
                    else:
                        # Unique so far, keep clean name
                        effective_name = original_name
                    
                    # Ensure tool returns a string (fixes 422 errors)
                    tool = self._wrap_tool_to_return_string(tool, new_name=effective_name)
                    
                    # Wrap with HITL if needed
                    # Note: My previous fix for Base Name Matching handles both clean and prefixed names!
                    if self._needs_hitl_wrapper(effective_name):
                        tool = self._wrap_tool_with_hitl(tool, name, new_name=effective_name)
                    
                    all_tools.append(tool)
                    used_names.add(effective_name)
                    
            except Exception as e:
                logger.error(f"Error getting tools for {name}: {e}")
                
        return all_tools

    def _wrap_tool_to_return_string(self, tool: StructuredTool, new_name: str = None) -> StructuredTool:
        """Wrap tool to ensure it returns a string (fixes 422 errors)."""
        original_coroutine = tool.coroutine
        
        async def string_wrapper(**kwargs):
            result = await original_coroutine(**kwargs)
            # If result is not a string, convert it
            if not isinstance(result, str):
                # Try to extract content if it's a message/artifact
                if hasattr(result, 'content') and isinstance(result.content, str):
                    return result.content
                return str(result)
            return result
            
        return StructuredTool.from_function(
            name=new_name or tool.name,
            description=tool.description,
            func=None,
            coroutine=string_wrapper,
            args_schema=tool.args_schema,
            handle_tool_error=True
        )

    def _needs_hitl_wrapper(self, tool_name: str) -> bool:
        """Check if tool needs HITL approval wrapper."""
        hitl_config = self.config_data.get("hitl_config", {})
        if not hitl_config.get("enabled", False):
            return False
        
        if tool_name in self.whitelisted_tools:
            return False
        
        mode = hitl_config.get("mode", "denylist")
        if mode == "allowlist":
            return True
        
        sensitive_tools = hitl_config.get("sensitive_tools", [])
        
        # Extract base name for global matching
        base_name = tool_name.split("__")[-1] if "__" in tool_name else tool_name
        
        return any(
            fnmatch.fnmatch(tool_name, pattern) or fnmatch.fnmatch(base_name, pattern) 
            for pattern in sensitive_tools
        )
    
    def _wrap_tool_with_hitl(self, tool: StructuredTool, server_name: str, new_name: str = None) -> StructuredTool:
        """Wrap a LangChain tool with HITL approval logic."""
        original_coroutine = tool.coroutine
        tool_name_for_logic = new_name or tool.name
        
        async def hitl_wrapper(**kwargs):
            # Manual HITL check (middleware will also catch this)
            await self._check_hitl_approval(tool_name_for_logic, kwargs)
            # Call original tool function
            if original_coroutine:
                return await original_coroutine(**kwargs)
            else:
                # Fallback to direct tool call (should not happen with langchain-mcp-adapters)
                return await self.call_tool(tool.name, kwargs, server_name=server_name)
        
        # Create new tool with wrapped coroutine
        return StructuredTool.from_function(
            name=tool_name_for_logic,
            description=tool.description,
            func=None,
            coroutine=hitl_wrapper,
            args_schema=tool.args_schema,
            handle_tool_error=True
        )

    def _compute_signature(self, tool_name: str, args: dict) -> str:
        """Compute deterministic signature for tool call."""
        try:
            # Sort keys for consistent hashing
            args_str = json.dumps(args, sort_keys=True, default=str)
            return f"{tool_name}:{args_str}"
        except Exception:
            # Fallback for non-serializable args
            return f"{tool_name}:{str(args)}"

    async def _check_hitl_approval(self, tool_name: str, tool_args: dict):
        """
        Manual HITL check as a backup to middleware.
        Raises ApprovalRequiredError if approval is needed.
        """
        sig = self._compute_signature(tool_name, tool_args)
        
        # If tool signature is whitelisted (recently approved same call), allow it ONCE then remove
        if sig in self.whitelisted_tools:
            # One-time approval policy
            self.whitelisted_tools.remove(sig)
            return

        # If it doesn't need approval according to config, return
        if not self._needs_hitl_wrapper(tool_name):
            return
            
        # If we reached here, the tool needs approval and is NOT whitelisted
        raise ApprovalRequiredError(
            tool_name=tool_name,
            tool_args=tool_args,
            message="Execution requires your approval."
        )


    async def call_tool(self, tool_name: str, arguments: dict, server_name: str) -> Any:
        """Execute a tool call via the session."""
        session = self.server_sessions.get(server_name)
        if not session:
             raise ValueError(f"Server {server_name} not connected.")

        try:
            result = await session.call_tool(tool_name, arguments)
            return self._process_tool_result(result)
        except ApprovalRequiredError:
            # Re-raise for the agent to catch
            raise
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Tool execution failed: {tool_name} - {error_msg}")
            return f"Error: Tool execution failed. {error_msg}"

    def _process_tool_result(self, result: Any) -> Any:
        """Extract text from MCP tool result."""
        if hasattr(result, 'content'):
             content_list = getattr(result, 'content', [])
             processed = []
             for item in content_list:
                if hasattr(item, 'text'):
                     processed.append(item.text)
                else:
                     processed.append(str(item))
             return "\n".join(processed)
        return str(result)

    async def get_all_tools_status(self) -> Dict[str, Any]:
        """Get status for UI dashboard."""
        status = {}
        mcp_servers = self.config_data.get("mcpServers", {})
        for s_name, server in mcp_servers.items():
            is_connected = s_name in self.server_sessions
            server_enabled = server.get("enabled", True)
            
            tool_list = []
            if is_connected:
                try:
                    # Get actual tools from session if connected
                    tools_obj = await self.server_sessions[s_name].list_tools()
                    # Convert to simple list of dicts/strings if needed, or just names
                    tool_list = [t.name for t in tools_obj]
                except: 
                    pass
            
            status[s_name] = {
                "enabled": server_enabled,
                "connected": is_connected,
                "tools_count": len(tool_list),
                "tools": tool_list,
                "disabled_tools": server.get("disabled_tools", [])
            }
        return status

    async def toggle_server_status(self, server_name: str, enable: bool) -> bool:
        """Enable or disable a server."""
        mcp_servers = self.config_data.get("mcpServers", {})
        if server_name not in mcp_servers:
            return False
            
        config = mcp_servers[server_name]
        config["enabled"] = enable
        
        # Persist to DB
        await self._save_config_to_db(server_name, config)
        
        # If disabling, disconnect
        if not enable:
            # We use pop with default to safely remove if exists, avoiding KeyErrors
            self.server_sessions.pop(server_name, None)
            
        return True

    async def disconnect_server(self, server_name: str):
        """Disconnect a server without removing from config."""
        if server_name in self.server_sessions:
             del self.server_sessions[server_name]
             logger.info(f"Disconnected server: {server_name}")

    async def inspect_server_tools(self, server_name: str) -> List[str]:
        """
        Connect to a server (if not connected) just to list tools, 
        but don't keep it in the active session list if it was disabled.
        """
        was_connected = server_name in self.server_sessions
        
        if not was_connected:
             mcp_servers = self.config_data.get("mcpServers", {})
             config = mcp_servers.get(server_name)
             if not config: return []
             await self.init_server(server_name, config)
             
        try:
            if server_name in self.server_sessions:
                tools = await self.server_sessions[server_name].list_tools()
                return [t.name for t in tools]
        except Exception as e:
            logger.error(f"Failed to inspect tools for {server_name}: {e}")
            return []
        finally:
            # If it wasn't connected before, maybe disconnect? 
            # actually keeping it connected is fine for cache, 
            # unless it's explicitly disabled.
            pass
        return []

    async def toggle_tool_status(self, tool_name: str, enable: bool) -> str:
        """Persistent toggle of a tool in config."""
        server_name = None
        for name, session in self.server_sessions.items():
            try:
                tools = await session.list_tools()
                if any(t.name == tool_name for t in tools):
                    server_name = name
                    break
            except: continue
            
        if not server_name:
            return f"Tool '{tool_name}' not found."

        mcp_servers = self.config_data.get("mcpServers", {})
        server_config = mcp_servers.get(server_name)
        if not server_config: return "Config not found."
             
        disabled_list = server_config.get("disabled_tools", [])
        if enable and tool_name in disabled_list:
            disabled_list.remove(tool_name)
        elif not enable and tool_name not in disabled_list:
            disabled_list.append(tool_name)
        
        server_config["disabled_tools"] = disabled_list
        await self._save_config_to_db(server_name, server_config)
        return f"Tool '{tool_name}' {'enabled' if enable else 'disabled'}."

    async def add_server(self, name: str, config: Dict[str, Any], validate: bool = False) -> bool:
        """Add a new server to the configuration and connect to it."""
        try:
            if validate:
                # 1. Initialize and Connect first
                await self.init_server(name, config)
                if name not in self.server_sessions:
                    return False
            
            # 2. Update Database
            await self._save_config_to_db(name, config)
            
            if not validate:
                # If we didn't validate (connect) above, do it now
                await self.init_server(name, config)
                
            return True
        except Exception as e:
            logger.error(f"Failed to add server {name}: {e}")
            return False

    async def remove_server(self, name: str) -> bool:
        """Remove a server from configuration and disconnect."""
        try:
            # 1. Disconnect if connected
            self.server_sessions.pop(name, None)
                
            # 2. Update Database
            async with AsyncSession(async_engine) as session:
                stmt = delete(MCPServerConfig).where(
                    MCPServerConfig.user_id == self.user_id,
                    MCPServerConfig.name == name
                )
                await session.execute(stmt)
                await session.commit()
            
            # Refresh cache
            await self._load_config_from_db()
            return True
        except Exception as e:
            logger.error(f"Failed to remove server {name}: {e}")
            return False

