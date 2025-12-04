import sys
import os
import asyncio
import warnings
from typing import Dict, Any
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from .base import MCPHandler
import logging

logger = logging.getLogger(__name__)

# Suppress the anyio cancel scope warnings that occur during cleanup
warnings.filterwarnings('ignore', message='.*cancel scope.*')

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
        """Disconnect from the MCP server with proper error handling."""
        if self.exit_stack:
            try:
                # Cancel any pending tasks first to avoid cancel scope errors
                await asyncio.sleep(0)  # Allow pending tasks to complete
                await self.exit_stack.aclose()
            except (RuntimeError, GeneratorExit, BaseExceptionGroup) as e:
                # Suppress expected cleanup errors during shutdown
                # These are normal when exiting and don't indicate a problem
                error_msg = str(e)
                if any(msg in error_msg for msg in ["cancel scope", "GeneratorExit", "unhandled errors in a TaskGroup"]):
                    # This is expected during cleanup, silently ignore
                    pass
                else:
                    logger.debug(f"Error during disconnect (expected during shutdown): {e}")
            except Exception as e:
                # Catch any other exceptions to prevent them from propagating
                logger.debug(f"Unexpected error during disconnect: {e}")
        self.session = None
        self.exit_stack = None
