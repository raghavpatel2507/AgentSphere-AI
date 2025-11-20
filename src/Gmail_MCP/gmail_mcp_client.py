"""
Gmail MCP Client
================
Simplified client for Gmail MCP server using stdio communication.
Follows the same pattern as GitHub MCP client.
"""

import asyncio
import os
from typing import Optional
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class GmailMCPClient:
    """Singleton client for Gmail MCP server"""
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self.server_script_path = "/home/logicrays/gmail-mcp/src/gmail/server.py"
            self.credentials_path = "/home/logicrays/Desktop/RAGHAV/AgentSphere-AI/src/Gmail_MCP/credential.json"
            self.token_path = "/home/logicrays/Desktop/RAGHAV/AgentSphere-AI/src/Gmail_MCP/token.json"
            self.session: Optional[ClientSession] = None
            self.exit_stack = AsyncExitStack()
            self.loop = None
            self.__class__._initialized = True
    
    async def _connect(self):
        """Internal async connection method"""
        if self.session is not None:
            return  # Already connected
        
        # Configure server parameters
        server_params = StdioServerParameters(
            command="python3",
            args=[
                self.server_script_path,
                "--creds-file-path", self.credentials_path,
                "--token-path", self.token_path
            ],
            env=None
        )
        
        # Create stdio client connection
        stdio_transport = await self.exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        
        # Create session
        self.session = await self.exit_stack.enter_async_context(
            ClientSession(stdio_transport[0], stdio_transport[1])
        )
        
        # Initialize session
        await self.session.initialize()
    
    def connect(self):
        """Synchronous wrapper for connection"""
        if self.loop is None:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
        
        if self.session is None:
            self.loop.run_until_complete(self._connect())
    
    async def _call_tool_async(self, tool_name: str, arguments: dict):
        """Internal async tool call"""
        if self.session is None:
            await self._connect()
        
        result = await self.session.call_tool(tool_name, arguments)
        
        # Extract content from MCP response
        if hasattr(result, 'content') and result.content:
            if isinstance(result.content, list) and len(result.content) > 0:
                content_item = result.content[0]
                if hasattr(content_item, 'text'):
                    return content_item.text
        
        return str(result)
    
    def call_tool(self, tool_name: str, arguments: dict):
        """Synchronous wrapper for tool calls"""
        if self.loop is None:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
        
        return self.loop.run_until_complete(
            self._call_tool_async(tool_name, arguments)
        )
    
    def close(self):
        """Close the connection"""
        if self.loop and self.exit_stack:
            self.loop.run_until_complete(self.exit_stack.aclose())
            self.session = None
