"""
FileSystem MCP Client
=====================
Thread-safe client for FileSystem MCP server using stdio communication.
Follows the same pattern as Gmail and Zoho MCP clients.
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


class FileSystemMCPClient:
    """Singleton client for FileSystem MCP server"""
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self.server_script_path = "src/mcp_servers/file-system-mcp-server/file-system-mcp-server/fs_server.py"
            self.session: Optional[ClientSession] = None
            self.exit_stack = AsyncExitStack()
            
            # Lock to serialize MCP requests (prevent parallel calls)
            self._request_lock = asyncio.Lock()
            
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
        
        try:
            # Configure server parameters
            server_params = StdioServerParameters(
                command=sys.executable,
                args=[
                    self.server_script_path,
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
            print("✅ FileSystem MCP server connected successfully")
        except Exception as e:
            print(f"❌ Failed to connect to FileSystem MCP server: {e}")
            self.session = None
            raise
    
    async def _reconnect(self):
        """Reconnect to the MCP server after connection loss"""
        print("🔄 Attempting to reconnect to FileSystem MCP server...")
        try:
            # Close existing connection
            if self.exit_stack:
                try:
                    await self.exit_stack.aclose()
                except Exception:
                    pass
            
            # Reset state
            self.session = None
            self.exit_stack = AsyncExitStack()
            
            # Reconnect
            await self._connect()
            print("✅ Reconnected to FileSystem MCP server")
        except Exception as e:
            print(f"❌ Reconnection failed: {e}")
            raise
    
    async def _call_tool(self, tool_name: str, arguments: dict):
        """Internal async tool call with automatic reconnection and request serialization"""
        # Acquire lock to serialize requests (prevent parallel calls)
        async with self._request_lock:
            max_retries = 2
            retry_count = 0
            
            while retry_count <= max_retries:
                try:
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
                    
                except Exception as e:
                    error_msg = str(e)
                    if "Connection closed" in error_msg or "connection" in error_msg.lower():
                        if retry_count < max_retries:
                            print(f"⚠️  Connection lost, retrying ({retry_count + 1}/{max_retries})...")
                            retry_count += 1
                            try:
                                await self._reconnect()
                                continue  # Retry the tool call
                            except Exception as reconnect_error:
                                print(f"❌ Reconnection failed: {reconnect_error}")
                        else:
                            print(f"❌ Max retries reached. FileSystem MCP server may have crashed.")
                            raise Exception(f"FileSystem MCP connection failed after {max_retries} retries: {error_msg}")
                    else:
                        # Non-connection error, raise immediately
                        print(f"❌ FileSystem MCP tool error: {error_msg}")
                        raise
            
            raise Exception("Failed to execute FileSystem tool after multiple retries")
        
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
