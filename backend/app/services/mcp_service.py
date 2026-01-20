"""
MCP Service for managing MCP server connections and tools.
Uses mcp-use + langchain-mcp-adapters like the existing codebase.
"""

import logging
import os
from typing import Any, Dict, List
from uuid import UUID

logger = logging.getLogger(__name__)


class MCPService:
    """Fast, stateless MCP tool listing service."""
    
    def __init__(self, user_id: UUID):
        self.user_id = user_id
    
    async def test_server_connection(self, server_name: str, config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Test connection and return list of tools."""
        import asyncio
        max_retries = 2
        
        for attempt in range(max_retries + 1):
            try:
                tools = await self.get_tools_for_server(server_name, config)
                if tools or attempt == max_retries:
                    return tools
                
                logger.info(f"Attempt {attempt + 1}: No tools found for {server_name}. Retrying in 2s...")
                await asyncio.sleep(2)
            except Exception as e:
                if attempt == max_retries:
                    logger.error(f"Test connection failed for {server_name} after {max_retries} retries: {e}")
                    raise
                logger.warning(f"Attempt {attempt + 1} failed for {server_name}: {e}. Retrying...")
                await asyncio.sleep(2)
        return []

    async def get_tools_for_server(self, server_name: str, config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get tools using session + langchain-mcp-adapters pattern with user-specific tokens."""
        from mcp_use import MCPClient
        from langchain_mcp_adapters.tools import load_mcp_tools
        from backend.app.core.mcp.token_manager import TokenManager
        
        client = None
        try:
            # Clone config to avoid modifying original
            config = config.copy()
            
            # Load OAuth token if needed
            if "auth" in config and isinstance(config["auth"], dict):
                if "callback_port" in config["auth"]:
                    # This server requires OAuth - load token from database
                    token_manager = TokenManager(self.user_id)
                    token_data = await token_manager.get_token(server_name)
                    if token_data and token_data.get("access_token"):
                        config["auth"]["token"] = token_data["access_token"]
                        logger.info(f"Loaded OAuth token for {server_name}")
            
            # Windows compatibility for npx
            if os.name == 'nt' and config.get("command") == "npx":
                config["command"] = "npx.cmd"

            # Create client with server config
            full_config = {"mcpServers": {server_name: config}}
            client = MCPClient(full_config)
            
            # Create session
            await client.create_session(server_name)
            session = client.get_session(server_name)
            
            if not session:
                logger.error(f"Failed to get session for {server_name}")
                return []
            
            # Create adapter (same pattern as MCPManager)
            class ListToolsResult:
                def __init__(self, tools):
                    self.tools = tools
                    self.nextCursor = None
            
            class SessionAdapter:
                def __init__(self, sess):
                    self.sess = sess
                async def list_tools(self, cursor: str = None):
                    # Robust handling of list_tools result
                    # Some servers/mcp-use versions return an object with .tools, some return a list
                    result = await self.sess.list_tools()
                    
                    # If it's already a ListToolsResult or has .tools attribute
                    if hasattr(result, 'tools'):
                        tools_list = result.tools
                    elif isinstance(result, list):
                        tools_list = result
                    else:
                        logger.warning(f"Unexpected list_tools result type for {server_name}: {type(result)}")
                        tools_list = []
                        
                    return ListToolsResult(tools_list)

                async def call_tool(self, name: str, arguments: dict, **kwargs):
                    return await self.sess.call_tool(name=name, arguments=arguments)
            
            adapter = SessionAdapter(session)
            mcp_tools = await load_mcp_tools(adapter)
            
            tools = []
            for tool in mcp_tools:
                # Handle args_schema - could be a Pydantic model or already a dict
                schema = None
                if hasattr(tool, 'args_schema') and tool.args_schema:
                    if hasattr(tool.args_schema, 'schema'):
                        schema = tool.args_schema.schema()
                    elif isinstance(tool.args_schema, dict):
                        schema = tool.args_schema
                
                tools.append({
                    "name": getattr(tool, 'name', 'unknown'),
                    "description": getattr(tool, 'description', None),
                    "inputSchema": schema,
                })
            
            return tools
            
        except Exception as e:
            logger.error(f"Failed to get tools for {server_name}: {e}")
            raise
        finally:
            if client:
                try:
                    await client.close_session(server_name)
                except:
                    pass
    
    async def cleanup(self):
        pass
