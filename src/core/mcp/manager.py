import os
import asyncio
import logging
import json
from typing import Dict, List, Any, Optional, Type
from pydantic import create_model, Field, BaseModel

# Import mcp-use components
from mcp_use.client import MCPClient
from langchain_core.tools import Tool, StructuredTool
from langgraph.types import interrupt
import fnmatch

class ApprovalRequiredError(Exception):
    """Raised when a tool call requires human approval."""
    def __init__(self, tool_name: str, tool_args: Dict[str, Any], message: str):
        self.tool_name = tool_name
        self.tool_args = tool_args
        self.message = message
        super().__init__(self.message)

# Import mcp-use middleware components
from mcp_use.client.middleware.middleware import Middleware, MiddlewareContext


logger = logging.getLogger(__name__)

class ApprovalMiddleware(Middleware):
    """Middleware to intercept sensitive tool calls and request approval."""
    def __init__(self, manager: 'MCPManager'):
        self.manager = manager

    async def process_request(self, context: MiddlewareContext):
        if context.request_type == "call_tool":
            tool_name = context.params.get("name")
            tool_args = context.params.get("arguments", {})
            
            # Check if this tool needs approval
            hitl_config = self.manager.config_data.get("hitl_config", {})
            if hitl_config.get("enabled", False):
                mode = hitl_config.get("mode", "denylist")
                sensitive_tools = hitl_config.get("sensitive_tools", [])
                
                requires_approval = False
                if mode == "all":
                    requires_approval = True
                elif mode == "denylist":
                    for pattern in sensitive_tools:
                        if fnmatch.fnmatch(tool_name, pattern):
                            requires_approval = True
                            break
                
                # Check whitelist (bypass HITL if tool_name in whitelisted_tools)
                if tool_name in self.manager.whitelisted_tools:
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
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MCPManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        # Standard configuration file
        self.config_path = "multi_server_config.json"
        
        # Central MCPClient to manage all servers
        self._mcp_client: Optional[MCPClient] = None
        
        # Map server_name -> MCPSession
        self.server_sessions: Dict[str, Any] = {}
        
        self.config_data = {}
        # Runtime cache for session-approved tools
        self.whitelisted_tools: set[str] = set()
        
        # Tool Definition Cache (server_name -> list[tool])
        self.tool_cache: Dict[str, List[Any]] = {}
        
        self._initialized = True

    def whitelist_tool(self, tool_name: str):
        """Add a tool to the session whitelist to bypass HITL."""
        self.whitelisted_tools.add(tool_name)
        logger.info(f"Tool {tool_name} whitelisted for this session.")
        
    def load_config(self) -> Dict[str, Any]:
        """Load configuration from file (multi_server_config.json)."""
        if not os.path.exists(self.config_path):
            logger.warning(f"Config file {self.config_path} not found.")
            return {"mcpServers": {}}
            
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return {"mcpServers": {}}

    def reload_config(self):
        """Reload configuration from disk."""
        logger.info("Reloading MCP configuration...")
        self.config_data = self.load_config()
        self.tool_cache = {}
        return self.config_data
            
    async def initialize(self):
        """
        Instant initialization. 
        Just prepares the client and loads config, doesn't connect yet.
        """
        logger.info("Initializing MCP Manager (Deferred Mode)...")
        self.config_data = self.load_config()
        
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
            self._mcp_client = MCPClient()
            
        mcp_servers = self.config_data.get("mcpServers", {})
        init_tasks = []
        
        for name in server_names:
            if name in self.server_sessions:
                continue
            
            config = mcp_servers.get(name)
            if not config:
                logger.warning(f"Server {name} not found in config.")
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
            logger.error(f"❌ Failed to connect to server {name}: {e}")

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
        """Connect to servers and get tools, converting to LangChain tools."""
        # Ensure targeted servers are connected
        await self.connect_to_servers(server_names)
        
        all_tools = []
        for name in server_names:
            session = self.server_sessions.get(name)
            if not session:
                continue
                
            try:
                mcp_tools = await session.list_tools()
                
                # Check for disabled tools in config
                mcp_servers = self.config_data.get("mcpServers", {})
                server_config = mcp_servers.get(name, {})
                disabled_tools = server_config.get("disabled_tools", [])
                
                for tool in mcp_tools:
                    if tool.name in disabled_tools:
                        continue
                    
                    lc_tool = self._create_langchain_tool(tool, name)
                    all_tools.append(lc_tool)
            except Exception as e:
                logger.error(f"Error getting tools for {name}: {e}")
                
        return all_tools

    def _create_langchain_tool(self, tool: Any, server_name: str) -> StructuredTool:
        """Convert MCP tool to LangChain StructuredTool."""
        args_schema = self._create_args_schema(tool.name, getattr(tool, "inputSchema", {}))
        
        async def _run(**kwargs):
            # HITL Wrapper Logic
            await self._check_hitl_approval(tool.name, kwargs)
            return await self.call_tool(tool.name, kwargs, server_name=server_name)

        return StructuredTool.from_function(
            name=tool.name,
            description=getattr(tool, "description", "") or "",
            func=None,
            coroutine=_run,
            args_schema=args_schema,
            handle_tool_error=True
        )

    def _create_args_schema(self, name: str, schema: Dict[str, Any]) -> Type[BaseModel]:
        """Dynamically create a Pydantic model from a JSON schema."""
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        
        fields = {}
        for field_name, field_info in properties.items():
            field_type = Any
            t = field_info.get("type")
            
            if t == "string": field_type = str
            elif t == "integer": field_type = int
            elif t == "boolean": field_type = bool
            elif t == "number": field_type = float
            elif t == "array": field_type = List[Any]
            elif t == "object": field_type = dict
                
            description = field_info.get("description", "")
            default = ... if field_name in required else None
            fields[field_name] = (field_type, Field(default=default, description=description))
            
        if not fields:
            return create_model(f"{name}Schema")
            
        return create_model(f"{name}Schema", **fields)

    async def _check_hitl_approval(self, tool_name: str, tool_args: dict):
        """
        Deprecated: HITL is now handled via ApprovalMiddleware.
        Keep for internal logic if needed, but the primary guard is the middleware.
        """
        pass

    async def call_tool(self, tool_name: str, arguments: dict, server_name: str) -> Any:
        """Execute a tool call via the specified server session."""
        session = self.server_sessions.get(server_name)
        if not session:
             raise ValueError(f"Server {server_name} not connected.")

        try:
            result = await session.call_tool(tool_name, arguments)
            return self._process_tool_result(result)
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
            status[s_name] = {
                "enabled": True, # Multi-server config doesn't have a top-level enabled flag usually, can be added
                "connected": s_name in self.server_sessions,
                "tools_count": 0
            }
            if status[s_name]["connected"]:
                try:
                    tools = await self.server_sessions[s_name].list_tools()
                    status[s_name]["tools_count"] = len(tools)
                except: pass
        return status

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
        self._save_config(self.config_data)
        return f"Tool '{tool_name}' {'enabled' if enable else 'disabled'}."

    def _save_config(self, config_data: dict):
        with open(self.config_path, 'w') as f:
            json.dump(config_data, f, indent=2)

