"""
Gmail MCP Client
================
Simplified client for Gmail MCP server using stdio communication.
Thread-safe version using a dedicated background event loop.
"""

import asyncio
import os
import sys
import threading
from typing import Optional, List
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import Tool as McpTool


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
            self.server_script_path = "src/mcp_servers/gmail-mcp/src/gmail/server.py"
            self.credentials_path = "src/configs/gmail_credential.json"
            self.token_path = "src/configs/gmail_token.json"
            self.session: Optional[ClientSession] = None
            self.exit_stack = AsyncExitStack()
            
            # Dedicated event loop for this client
            self._loop = asyncio.new_event_loop()
            self._thread = threading.Thread(target=self._start_loop, daemon=True)
            self._thread.start()
            
            self.__class__._initialized = True
            
    def _start_loop(self):
        """Run the dedicated event loop in a background thread."""
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()
    
    async def _connect(self):
        """Connect to the MCP server (Async)"""
        if self.session is not None:
            return  # Already connected
        
        # Configure server parameters
        server_params = StdioServerParameters(
            command=sys.executable,
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
    
    async def _call_tool(self, tool_name: str, arguments: dict):
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
        
    async def _list_tools(self) -> List[McpTool]:
        if self.session is None:
            await self._connect()
        result = await self.session.list_tools()
        return result.tools
    
    # ------------------------------------------------------
    # Sync wrappers (Thread-Safe)
    # ------------------------------------------------------
    def connect_sync(self):
        """Synchronous wrapper for connection"""
        future = asyncio.run_coroutine_threadsafe(self._connect(), self._loop)
        return future.result()
    
    def call_tool_sync(self, tool_name: str, arguments: dict):
        """Synchronous wrapper for tool calls"""
        future = asyncio.run_coroutine_threadsafe(
            self._call_tool(tool_name, arguments), self._loop
        )
        return future.result()
        
    def list_tools_sync(self) -> List[McpTool]:
        """Synchronous wrapper for listing tools"""
        future = asyncio.run_coroutine_threadsafe(self._list_tools(), self._loop)
        return future.result()
    
    async def _close(self):
        """Close the connection (Async)"""
        if self.exit_stack:
            try:
                await self.exit_stack.aclose()
            except Exception:
                pass  # Ignore cleanup errors
            self.session = None
            
    def close_sync(self):
        """Close the connection (Sync)"""
        if self._loop and self.exit_stack:
            future = asyncio.run_coroutine_threadsafe(self._close(), self._loop)
            try:
                return future.result(timeout=5)
            except Exception:
                pass  # Ignore cleanup errors
