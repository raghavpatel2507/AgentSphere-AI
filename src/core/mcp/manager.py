import json
import os
import asyncio
import logging
from typing import Dict, List, Any, Optional
from .tool_registry import ToolRegistry
from .handlers.base import MCPHandler
from .handlers.node_handler import NodeMCPHandler
from .handlers.python_handler import PythonMCPHandler
from .handlers.docker_handler import DockerMCPHandler
from .handlers.remote_handler import RemoteMCPHandler
from .handlers.http_handler import HttpMCPHandler

logger = logging.getLogger(__name__)

class MCPManager:
    """
    Universal MCP Manager.
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
        self.registry = ToolRegistry()
        self.handlers: Dict[str, MCPHandler] = {}
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
        """Initialize all enabled MCP servers."""
        config = self.load_config()
        servers = config.get("mcp_servers", [])
        
        init_tasks = []
        
        for server_config in servers:
            if not server_config.get("enabled", False):
                continue
                
            name = server_config.get("name")
            server_type = server_config.get("type")
            
            handler = self._create_handler(server_type, server_config)
            if handler:
                self.handlers[name] = handler
                init_tasks.append(self._init_server(name, handler))
                
        if init_tasks:
            await asyncio.gather(*init_tasks, return_exceptions=True)

    def _create_handler(self, server_type: str, config: Dict[str, Any]) -> Optional[MCPHandler]:
        """Factory method to create appropriate handler."""
        if server_type == "node":
            return NodeMCPHandler(config)
        elif server_type == "python":
            return PythonMCPHandler(config)
        elif server_type == "docker":
            return DockerMCPHandler(config)
        elif server_type == "remote":
            return RemoteMCPHandler(config)
        elif server_type == "httpx":
            return HttpMCPHandler(config)
        else:
            logger.error(f"Unknown server type: {server_type}")
            return None
            
    async def _init_server(self, name: str, handler: MCPHandler):
        """Initialize a single server and register its tools."""
        try:
            logger.info(f"Initializing MCP server: {name}")
            await handler.connect()
            
            tools = await handler.list_tools()
            for tool in tools:
                self.registry.register_tool(
                    server_name=name,
                    tool_name=tool.name,
                    description=tool.description or "",
                    schema=tool.inputSchema
                )
                
            logger.info(f"Initialized {name} with {len(tools)} tools")
            
        except Exception as e:
            logger.error(f"Failed to initialize server {name}: {e}")
            
    async def cleanup(self):
        """Disconnect all servers."""
        tasks = [handler.disconnect() for handler in self.handlers.values()]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
            
    def get_tool(self, tool_name: str):
        """Get tool info from registry."""
        return self.registry.get_tool(tool_name)
        
    async def call_tool(self, tool_name: str, arguments: dict) -> Any:
        """Route tool call to appropriate server."""
        tool_info = self.registry.get_tool(tool_name)
        if not tool_info:
            raise ValueError(f"Tool {tool_name} not found")
            
        handler = self.handlers.get(tool_info.server_name)
        if not handler:
            raise ValueError(f"Server {tool_info.server_name} not found for tool {tool_name}")
            
        # Use original tool name for the actual call (strip prefix if added)
        result = await handler.call_tool(tool_info.original_name, arguments)
        return self._process_tool_result(result)

    def _process_tool_result(self, result: Any) -> Any:
        """
        Process tool result to handle large outputs (e.g. base64 images).
        If a large base64 string is found, save it to a file and return the path.
        """
        import base64
        import uuid
        
        # Threshold for "large" output (e.g. 10KB)
        LARGE_OUTPUT_THRESHOLD = 10000
        
        if isinstance(result, list):
            # MCP tools often return a list of content objects
            processed_list = []
            for item in result:
                if isinstance(item, dict):
                    # Check for base64 image content
                    if item.get("type") == "image" and "data" in item:
                        data = item["data"]
                        if len(data) > LARGE_OUTPUT_THRESHOLD:
                            try:
                                # Create screenshots directory if it doesn't exist
                                os.makedirs("screenshots", exist_ok=True)
                                
                                # Generate filename
                                filename = f"screenshot_{uuid.uuid4()}.png"
                                filepath = os.path.join("screenshots", filename)
                                
                                # Decode and save
                                with open(filepath, "wb") as f:
                                    f.write(base64.b64decode(data))
                                    
                                # Replace data with file path reference
                                item_copy = item.copy()
                                item_copy["data"] = f"[Image saved to {os.path.abspath(filepath)}]"
                                item_copy["saved_to"] = os.path.abspath(filepath)
                                processed_list.append(item_copy)
                                continue
                            except Exception as e:
                                logger.error(f"Failed to save image: {e}")
                                # If saving fails, we might still want to truncate it to avoid crashing
                                item_copy = item.copy()
                                item_copy["data"] = "[Image data too large and failed to save]"
                                processed_list.append(item_copy)
                                continue
                    
                    # Check for large text content
                    elif item.get("type") == "text" and "text" in item:
                        text = item["text"]
                        if len(text) > LARGE_OUTPUT_THRESHOLD * 10: # Allow more for text
                             # We could truncate or save text too, but usually images are the main culprit
                             pass

                processed_list.append(item)
            return processed_list
            
        return result
        
    def get_all_tools(self):
        """Get all registered tools."""
        return self.registry.get_all_tools()
        
    def get_tools_for_server(self, server_name: str):
        """Get tools for a specific server."""
        return self.registry.get_tools_by_server(server_name)
