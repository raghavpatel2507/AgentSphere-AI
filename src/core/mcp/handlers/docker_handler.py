import os
from typing import Dict, Any
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from .base import MCPHandler
import logging

logger = logging.getLogger(__name__)

class DockerMCPHandler(MCPHandler):
    """
    Handler for Docker based MCP servers.
    Uses stdio communication via 'docker run -i'.
    """
    
    async def connect(self):
        try:
            # Command is always docker
            command = "docker"
            
            # Base args for interactive mode
            base_args = ["run", "-i", "--rm"]
            
            # Add env vars to docker command
            env_args = []
            if "env" in self.config:
                for key, value in self.config["env"].items():
                    # Handle env var substitution
                    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                        env_var_name = value[2:-1]
                        env_value = os.getenv(env_var_name)
                        if env_value:
                            env_args.extend(["-e", f"{key}={env_value}"])
                    else:
                        env_args.extend(["-e", f"{key}={value}"])
            
            # User provided args (image name, etc.)
            user_args = self.config.get("args", [])
            
            # Combine all args
            full_args = base_args + env_args + user_args
            
            server_params = StdioServerParameters(
                command=command,
                args=full_args,
                env=None, # Env is passed via docker args
                cwd=None
            )
            
            self.exit_stack = AsyncExitStack()
            
            stdio_transport = await self.exit_stack.enter_async_context(
                stdio_client(server_params)
            )
            
            self.session = await self.exit_stack.enter_async_context(
                ClientSession(stdio_transport[0], stdio_transport[1])
            )
            
            await self.session.initialize()
            logger.info(f"Connected to Docker MCP server: {self.name}")
            
        except Exception as e:
            logger.error(f"Failed to connect to Docker MCP server {self.name}: {e}")
            await self.disconnect()
            raise
            
    async def disconnect(self):
        """Disconnect from the MCP server with proper error handling."""
        if self.exit_stack:
            try:
                await self.exit_stack.aclose()
            except (RuntimeError, GeneratorExit, Exception) as e:
                # Suppress expected cleanup errors during shutdown
                # These are normal when exiting and don't indicate a problem
                if "cancel scope" not in str(e) and "GeneratorExit" not in str(e):
                    logger.debug(f"Error during disconnect (expected during shutdown): {e}")
        self.session = None
        self.exit_stack = None
