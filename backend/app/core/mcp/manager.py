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
from typing import Dict, List, Any, Optional

from mcp_use.client import MCPClient
from langchain_core.tools import StructuredTool
from langchain_mcp_adapters.tools import load_mcp_tools

from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.db import async_engine
from backend.app.core.state.models import User, MCPServerConfig
from backend.app.core.auth.security import decrypt_config, encrypt_config

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
                    # Trigger connection in background so it's ready "instantly"
                    asyncio.create_task(self._connect_single(name, self._server_configs[name]))
                else:
                    # Disconnect immediately if disabled
                    await self.disconnect_server(name)
                
                return True
        return False
        
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
            resolved_config = config
            
            # Windows fix
            if os.name == 'nt' and resolved_config.get("command") == "npx":
                resolved_config["command"] = "npx.cmd"

            # mcp-use: Register then Connect
            self._client.add_server(name, resolved_config)
            self._sessions[name] = await self._client.create_session(name)
            
            logger.info(f"✅ Connected: {name}")
        except Exception as e:
            logger.error(f"❌ Connection failed for {name}: {e}")

    async def disconnect_server(self, name: str):
        """Disconnect active session."""
        if name in self._sessions:
            # mcp-use doesn't expose strict per-session disconnect, 
            # usually handled by removing session ref or closing client.
            # For now we just remove from our tracking.
            self._sessions.pop(name, None)

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
