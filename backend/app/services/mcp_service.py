"""
MCP Service for managing MCP server connections and tools.
Wraps the existing MCPManager for API use.
"""

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

logger = logging.getLogger(__name__)


class MCPService:
    """
    Service layer for MCP operations.
    Wraps the existing MCPManager for stateless API use.
    """
    
    def __init__(self, user_id: UUID):
        self.user_id = user_id
        self._manager = None
    
    async def _get_manager(self):
        """Lazy load the MCPManager."""
        if self._manager is None:
            try:
                from src.core.mcp.manager import MCPManager
                self._manager = MCPManager(self.user_id)
                await self._manager.initialize()
            except Exception as e:
                logger.error(f"Failed to initialize MCPManager: {e}")
                raise
        return self._manager
    
    async def test_server_connection(self, server_name: str, config: Dict[str, Any]) -> int:
        """
        Test connection to an MCP server.
        
        Returns the number of tools available.
        """
        try:
            from mcp_use.client import MCPClient
            
            # Create a temporary client for testing
            temp_config = {"mcpServers": {server_name: config}}
            client = MCPClient(temp_config)
            
            # Try to connect
            await client.create_session(server_name)
            
            # Get session and list tools
            session = client.get_session(server_name)
            if session:
                tools_result = await session.list_tools()
                tools_count = len(tools_result.tools) if tools_result else 0
                
                # Cleanup
                await client.close_session(server_name)
                
                return tools_count
            
            return 0
        except Exception as e:
            logger.error(f"Connection test failed for {server_name}: {e}")
            raise
    
    async def get_tools_for_server(self, server_name: str, config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Get available tools for a specific server.
        
        Returns list of tool definitions.
        """
        try:
            from mcp_use.client import MCPClient
            
            temp_config = {"mcpServers": {server_name: config}}
            client = MCPClient(temp_config)
            
            await client.create_session(server_name)
            session = client.get_session(server_name)
            
            if session:
                tools_result = await session.list_tools()
                tools = []
                
                if tools_result and tools_result.tools:
                    for tool in tools_result.tools:
                        tools.append({
                            "name": tool.name,
                            "description": getattr(tool, 'description', None),
                            "inputSchema": getattr(tool, 'inputSchema', None),
                        })
                
                await client.close_session(server_name)
                return tools
            
            return []
        except Exception as e:
            logger.error(f"Failed to get tools for {server_name}: {e}")
            raise
    
    async def cleanup(self):
        """Cleanup manager resources."""
        if self._manager:
            await self._manager.cleanup()
            self._manager = None
