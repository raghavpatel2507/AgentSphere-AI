from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class ToolInfo:
    name: str
    description: str
    schema: Dict[str, Any]
    server_name: str
    original_name: str

class ToolRegistry:
    """
    Central registry for all MCP tools.
    Maps tool names to their source MCP servers and handles conflicts.
    """
    
    def __init__(self):
        self._tools: Dict[str, ToolInfo] = {}
        self._server_tools: Dict[str, List[str]] = {}
        
    def register_tool(self, server_name: str, tool_name: str, description: str, schema: Dict[str, Any]) -> str:
        """
        Register a tool from an MCP server.
        Returns the registered tool name (may be prefixed if conflict exists).
        """
        final_name = tool_name
        
        # Handle name conflicts
        if final_name in self._tools and self._tools[final_name].server_name != server_name:
            # Conflict detected, prefix with server name
            final_name = f"{server_name}_{tool_name}"
            logger.warning(f"Tool name conflict: '{tool_name}' exists. Renaming to '{final_name}'")
            
        # Store tool info
        tool_info = ToolInfo(
            name=final_name,
            description=description,
            schema=schema,
            server_name=server_name,
            original_name=tool_name
        )
        
        self._tools[final_name] = tool_info
        
        # Update server mapping
        if server_name not in self._server_tools:
            self._server_tools[server_name] = []
        self._server_tools[server_name].append(final_name)
        
        return final_name
        
    def get_tool(self, tool_name: str) -> Optional[ToolInfo]:
        """Get tool information by name."""
        return self._tools.get(tool_name)
        
    def get_tools_by_server(self, server_name: str) -> List[ToolInfo]:
        """Get all tools for a specific server."""
        tool_names = self._server_tools.get(server_name, [])
        return [self._tools[name] for name in tool_names]
        
    def get_all_tools(self) -> List[ToolInfo]:
        """Get all registered tools."""
        return list(self._tools.values())
        
    def clear_server_tools(self, server_name: str):
        """Remove all tools for a specific server."""
        if server_name in self._server_tools:
            for tool_name in self._server_tools[server_name]:
                if tool_name in self._tools:
                    del self._tools[tool_name]
            del self._server_tools[server_name]

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """Get schemas for all tools in a format suitable for LLMs."""
        schemas = []
        for tool in self._tools.values():
            schemas.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.schema
                }
            })
        return schemas
