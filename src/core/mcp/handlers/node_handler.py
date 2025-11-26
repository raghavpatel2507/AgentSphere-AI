import sys
import os
from typing import Dict, Any
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from .base import MCPHandler
import logging

logger = logging.getLogger(__name__)

class NodeMCPHandler(MCPHandler):
    """
    Handler for Node.js based MCP servers.
    Uses stdio communication.
    """
    
    async def connect(self):
        try:
            command = self.config.get("command", "npx")
            args = self.config.get("args", [])
            env = os.environ.copy()
            
            # Add custom env vars
            if "env" in self.config:
                for key, value in self.config["env"].items():
                    # Handle env var substitution
                    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                        env_var_name = value[2:-1]
                        env_value = os.getenv(env_var_name)
                        if env_value:
                            env[key] = env_value
                        else:
                            logger.warning(f"Environment variable {env_var_name} not found for {self.name}")
                    else:
                        env[key] = str(value)
            
            cwd = self.config.get("cwd", None)
            
            server_params = StdioServerParameters(
                command=command,
                args=args,
                env=env,
                cwd=cwd
            )
            
            self.exit_stack = AsyncExitStack()
            
            stdio_transport = await self.exit_stack.enter_async_context(
                stdio_client(server_params)
            )
            
            self.session = await self.exit_stack.enter_async_context(
                ClientSession(stdio_transport[0], stdio_transport[1])
            )
            
            await self.session.initialize()
            logger.info(f"Connected to Node MCP server: {self.name}")
            
        except Exception as e:
            logger.error(f"Failed to connect to Node MCP server {self.name}: {e}")
            await self.disconnect()
            raise
            
    async def disconnect(self):
        if self.exit_stack:
            await self.exit_stack.aclose()
        self.session = None
        self.exit_stack = None
