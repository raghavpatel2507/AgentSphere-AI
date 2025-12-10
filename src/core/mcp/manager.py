import os
import asyncio
import logging
import json
from typing import Dict, List, Any, Optional, Type
from pydantic import create_model, Field, BaseModel

# Import mcp-use components
from mcp_use.client import MCPClient
from langchain_core.tools import Tool, StructuredTool

logger = logging.getLogger(__name__)

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
            
        self.config_path = "mcp_config.json"
        
        # Central MCPClient to manage all servers
        self._mcp_client: Optional[MCPClient] = None
        
        # Map server_name -> MCPSession
        self.server_sessions: Dict[str, Any] = {}
        
        self.config_data = {}
        self._initialized = True
        
    def load_config(self) -> Dict[str, Any]:
        """Load configuration from file."""
        if not os.path.exists(self.config_path):
            logger.warning(f"Config file {self.config_path} not found.")
            return {"mcp_servers": []}
            
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return {"mcp_servers": []}
            
    async def initialize(self):
        """Initialize all enabled MCP servers using mcp-use."""
        logger.info("Initializing MCP Manager with mcp-use...")
        
        # Initialize the client
        self._mcp_client = MCPClient()
        
        self.config_data = self.load_config()
        servers = self.config_data.get("mcp_servers", [])
        
        init_tasks = []
        
        for server_config in servers:
            if not server_config.get("enabled", False):
                continue
            
            name = server_config.get("name")
            init_tasks.append(self.init_server(name, server_config))
            
        if init_tasks:
            await asyncio.gather(*init_tasks, return_exceptions=True)
            
    def _resolve_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve environment variables in configuration."""
        resolved = config.copy()
        
        # Resolve 'env' dictionary
        if "env" in resolved:
            env = resolved["env"].copy()
            for k, v in env.items():
                if isinstance(v, str) and v.startswith("${") and v.endswith("}"):
                    var_name = v[2:-1]
                    val = os.getenv(var_name)
                    if val:
                        env[k] = val
            resolved["env"] = env
            
        # Resolve 'headers' dictionary
        if "headers" in resolved:
            headers = resolved["headers"].copy()
            for k, v in headers.items():
                if isinstance(v, str) and v.startswith("${") and v.endswith("}"):
                    var_name = v[2:-1]
                    val = os.getenv(var_name)
                    if val:
                        headers[k] = val
            resolved["headers"] = headers
            
        # StdioConnector in mcp-use doesn't support 'cwd'
        if "cwd" in resolved:
            del resolved["cwd"]
            
        return resolved

    async def init_server(self, name: str, config: Dict[str, Any]):
        """Initialize a single MCP server."""
        if self._mcp_client is None:
            self._mcp_client = MCPClient()

        try:
            # Check if server is enabled
            if not config.get("enabled", False):
                return

            # Resolve configuration
            server_config = self._resolve_config(config)

            # Windows compatibility for npx
            if os.name == 'nt' and server_config.get("command") == "npx":
                server_config["command"] = "npx.cmd"
            
            # Add server to client
            # mcp-use expects config to have specific keys depending on type
            # For stdio: command, args, env
            # For http: url (mapped to base_url maybe?), headers
            self._mcp_client.add_server(name, server_config)
            
            # Create and initialize session
            session = await self._mcp_client.create_session(name)
            
            self.server_sessions[name] = session
            logger.info(f"Initialized client for server: {name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize server {name}: {e}")

    async def cleanup(self):
        """Disconnect all servers."""
        if self._mcp_client:
            # close_all_sessions exists on client
            try:
                await self._mcp_client.close_all_sessions()
            except:
                pass
            self._mcp_client = None
        self.server_sessions.clear()

    def _create_args_schema(self, name: str, schema: Dict[str, Any]) -> Type[BaseModel]:
        """
        Dynamically create a Pydantic model from a JSON schema.
        Copied from ExpertFactory to support tool conversion logic here.
        """
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        
        fields = {}
        for field_name, field_info in properties.items():
            field_type = Any
            t = field_info.get("type")
            
            # Basic type mapping
            if t == "string":
                field_type = str
            elif t == "integer":
                field_type = int
            elif t == "boolean":
                field_type = bool
            elif t == "number":
                field_type = float
            elif t == "array":
                items = field_info.get("items", {})
                if not items or not isinstance(items, dict):
                    field_type = List[str]
                else:
                    item_type = items.get("type")
                    if not item_type:
                        if items.get("properties") or items.get("oneOf") or items.get("anyOf"):
                            field_type = List[dict]
                        else:
                            field_type = List[str]
                    elif item_type == "integer":
                        field_type = List[int]
                    elif item_type == "boolean":
                        field_type = List[bool]
                    elif item_type == "number":
                        field_type = List[float]
                    elif item_type == "object":
                        field_type = List[dict]
                    else:
                        field_type = List[str]
            elif t == "object":
                field_type = dict
                
            description = field_info.get("description", "")
            
            # Determine default value
            if field_name in required:
                default = ...
            else:
                default = None
                
            fields[field_name] = (field_type, Field(default=default, description=description))
            
        # If no properties, return empty model
        if not fields:
            return create_model(f"{name}Schema")
            
        return create_model(f"{name}Schema", **fields)

    async def get_tools_for_server(self, server_name: str) -> List[StructuredTool]:
        """Get tools for a specific server, converting to LangChain tools."""
        session = self.server_sessions.get(server_name)
        if not session:
            # Silent return or log warning
            return []
            
        try:
            # Get tools from session
            mcp_tools = await session.list_tools()
            
            # Load config to check for disabled tools
            full_config = self.load_config()
            server_config = next((s for s in full_config.get("mcp_servers", []) if s["name"] == server_name), {})
            disabled_tools = server_config.get("disabled_tools", [])
            
            lc_tools = []
            for tool in mcp_tools:
                if tool.name in disabled_tools:
                    continue
                    
                # Setup args schema
                # tool.inputSchema is the JSON schema
                args_schema = self._create_args_schema(tool.name, getattr(tool, "inputSchema", {}))
                
                # Create callable wrapper
                # We need to bind the specific session and tool name
                
                async def _make_run_func(s_name=server_name, t_name=tool.name):
                    async def _run(**kwargs):
                        return await self.call_tool(t_name, kwargs, server_name=s_name)
                    return _run

                lc_tool = StructuredTool.from_function(
                    name=tool.name,
                    description=getattr(tool, "description", "") or "",
                    func=None,
                    coroutine=await _make_run_func(),
                    args_schema=args_schema
                )
                
                lc_tools.append(lc_tool)
                
            return lc_tools
            
        except Exception as e:
            logger.error(f"Error getting tools for {server_name}: {e}")
            return []

    async def call_tool(self, tool_name: str, arguments: dict, server_name: str = None) -> Any:
        """
        Call a tool. 
        If server_name is provided, use that session.
        Otherwise, scan sessions (slower/risky).
        """
        session = None
        
        if server_name:
            session = self.server_sessions.get(server_name)
            if not session:
                 raise ValueError(f"Server {server_name} not found or not connected.")
        else:
            # Find strategy
            # Since we don't have a map...
            pass
            
        if not session:
             raise ValueError("server_name is required for call_tool")

        try:
            result = await session.call_tool(tool_name, arguments)
            return self._process_tool_result(result)
        except Exception as e:
            raise e

    def _process_tool_result(self, result: Any) -> Any:
        """Handle large outputs"""
        import base64
        import uuid
        LARGE_OUTPUT_THRESHOLD = 50000 
        
        # mcp-use result is CallToolResult
        if hasattr(result, 'content'):
             # It's an object
             content_list = getattr(result, 'content', [])
             processed = []
             
             for item in content_list:
                # item is TextContent or ImageContent
                if hasattr(item, 'type') and item.type == 'image':
                    data = getattr(item, 'data', "")
                    if len(data) > LARGE_OUTPUT_THRESHOLD:
                         # Save logic
                         filename = f"screenshot_{uuid.uuid4()}.png"
                         filepath = os.path.join("screenshots", filename)
                         os.makedirs("screenshots", exist_ok=True)
                         with open(filepath, "wb") as f:
                             f.write(base64.b64decode(data))
                         processed.append(f"[Image saved to {os.path.abspath(filepath)}]")
                    else:
                         processed.append("[Image data]")
                elif hasattr(item, 'text'):
                     processed.append(item.text)
                else:
                     processed.append(str(item))
             
             return "\n".join(processed)

        return str(result)
