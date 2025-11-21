"""
Filesystem MCP Client
=====================
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


class FilesystemMCPClient:
    """
    Singleton MCP client for Filesystem MCP Server.
    Uses a dedicated background thread for all async operations to ensure thread safety.
    """

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
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

    # ------------------------------------------------------
    # Connect to MCP Server (Async implementation)
    # ------------------------------------------------------
    async def _connect(self):
        if self.session is not None:
            return

        # Path to the Filesystem MCP server
        # The server is located at src/mcp_servers/filesystem-mcp/dist/index.js
        # We need to resolve the absolute path
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # Navigate up to src/ (current_dir is src/mcp_clients/Filesystem, so go up twice)
        mcp_clients_dir = os.path.dirname(current_dir)  # src/mcp_clients
        src_dir = os.path.dirname(mcp_clients_dir)  # src/
        server_path = os.path.join(src_dir, "mcp_servers", "filesystem-mcp", "dist", "index.js")

        if not os.path.exists(server_path):
             raise FileNotFoundError(f"Filesystem MCP server not found at: {server_path}")

        # Define allowed directories for the filesystem MCP
        # For safety, we can restrict it to the project root or specific folders
        # Here we'll allow the project root
        project_root = os.path.dirname(src_dir)
        
        # The filesystem MCP typically takes allowed directories as arguments
        # Check the server implementation or documentation if arguments are needed
        # Based on standard filesystem MCPs, they often take the allowed directory as an argument
        
        server_params = StdioServerParameters(
            command="node",
            args=[server_path, project_root], 
            env=os.environ.copy(),
        )

        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))

        self.session = await self.exit_stack.enter_async_context(
            ClientSession(stdio_transport[0], stdio_transport[1])
        )

        await self.session.initialize()

    # ------------------------------------------------------
    # Call MCP Tool (Async implementation)
    # ------------------------------------------------------
    async def _call_tool(self, tool_name: str, arguments: dict):
        if self.session is None:
            await self._connect()

        response = await self.session.call_tool(tool_name, arguments)

        # Extract text output
        if hasattr(response, "content") and response.content:
            item = response.content[0]
            if hasattr(item, "text"):
                return item.text

        return str(response)
        
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

    # ------------------------------------------------------
    # Close session
    # ------------------------------------------------------
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
