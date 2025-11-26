from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import asyncio
import logging
from mcp import ClientSession
from mcp.types import Tool as McpTool

logger = logging.getLogger(__name__)

class MCPHandler(ABC):
    """
    Abstract base class for MCP server handlers.
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.name = config.get("name", "unknown")
        self.session: Optional[ClientSession] = None
        self.exit_stack = None
        self._lock = asyncio.Lock()
        
    @abstractmethod
    async def connect(self):
        """Establish connection to the MCP server."""
        pass
        
    @abstractmethod
    async def disconnect(self):
        """Close connection to the MCP server."""
        pass
        
    async def reconnect(self):
        """Reconnect to the MCP server."""
        logger.info(f"Reconnecting to MCP server: {self.name}")
        await self.disconnect()
        await self.connect()
        
    async def list_tools(self) -> List[McpTool]:
        """List available tools from the server."""
        if not self.session:
            await self.connect()
            
        try:
            result = await self.session.list_tools()
            return result.tools
        except Exception as e:
            logger.error(f"Error listing tools for {self.name}: {e}")
            # Try one reconnection
            try:
                await self.reconnect()
                result = await self.session.list_tools()
                return result.tools
            except Exception as retry_err:
                logger.error(f"Retry failed for {self.name}: {retry_err}")
                raise
                
    async def call_tool(self, tool_name: str, arguments: dict) -> Any:
        """Call a specific tool on the server."""
        async with self._lock:
            if not self.session:
                await self.connect()
                
            try:
                result = await self.session.call_tool(tool_name, arguments)
                
                # Extract content from MCP response
                if hasattr(result, 'content') and result.content:
                    # Return the first text content found
                    for content in result.content:
                        if hasattr(content, 'text'):
                            return content.text
                    return str(result.content)
                
                return str(result)
                
            except Exception as e:
                error_msg = str(e)
                if "Connection closed" in error_msg or "connection" in error_msg.lower():
                    logger.warning(f"Connection lost for {self.name}, retrying...")
                    await self.reconnect()
                    # Retry once
                    result = await self.session.call_tool(tool_name, arguments)
                    if hasattr(result, 'content') and result.content:
                        for content in result.content:
                            if hasattr(content, 'text'):
                                return content.text
                        return str(result.content)
                    return str(result)
                else:
                    raise
