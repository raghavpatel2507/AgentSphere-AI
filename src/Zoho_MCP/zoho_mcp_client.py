"""
Zoho Books MCP Client
=====================
Fully fixed version — supports:
✔ access_token + refresh_token
✔ correct env passing
✔ no authentication errors
✔ auto loading credentials
"""

import asyncio
import json
import os
import threading
from typing import Optional
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class ZohoMCPClient:
    """
    Singleton MCP client for Zoho MCP Server.
    Thread-safe version using a dedicated background event loop.
    """

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.credentials_file = "/home/logicrays/Desktop/RAGHAV/AgentSphere-AI/src/Zoho_MCP/credentials.json"
            self.token_file = "/home/logicrays/Desktop/RAGHAV/AgentSphere-AI/src/Zoho_MCP/token.json"

            self.client_id: Optional[str] = None
            self.client_secret: Optional[str] = None
            self.organization_id: Optional[str] = None
            self.region: str = "US"

            self.access_token: Optional[str] = None
            self.refresh_token: Optional[str] = None

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
    # Load Credentials (access_token + refresh_token)
    # ------------------------------------------------------
    def _load_credentials(self):
        if not os.path.exists(self.credentials_file):
            raise FileNotFoundError(f"Missing credentials.json: {self.credentials_file}")

        with open(self.credentials_file, "r") as f:
            creds = json.load(f)

        self.client_id = creds["client_id"]
        self.client_secret = creds["client_secret"]
        self.organization_id = creds.get("organization_id", "")
        self.region = creds.get("region", "US")

        if not os.path.exists(self.token_file):
            raise FileNotFoundError(
                f"Missing token.json: {self.token_file}. Run authenticate_zoho.py first."
            )

        with open(self.token_file, "r") as f:
            token_data = json.load(f)

        self.refresh_token = token_data.get("refresh_token")
        self.access_token = token_data.get("access_token")

        if not self.refresh_token:
            raise ValueError("refresh_token missing in token.json")

        if not self.access_token:
            raise ValueError("access_token missing in token.json — re-run authenticate_zoho.py")

    # ------------------------------------------------------
    # Connect to MCP Server (Async implementation)
    # ------------------------------------------------------
    async def _connect(self):
        if self.session is not None:
            return

        # Load credentials lazily
        if self.client_id is None or self.refresh_token is None:
            self._load_credentials()

        # Detect your local zoho-mcp folder
        server_project_root = "/home/logicrays/Desktop/RAGHAV/AgentSphere-AI/src/external_zoho_mcp"
        server_module_dir = server_project_root
        server_module = "zoho_mcp.server"

        use_local = os.path.exists(f"{server_project_root}/zoho_mcp/server.py")

        if use_local:
            env = {
                "PYTHONPATH": server_module_dir,
                "ZOHO_CLIENT_ID": self.client_id,
                "ZOHO_CLIENT_SECRET": self.client_secret,
                "ZOHO_REFRESH_TOKEN": self.refresh_token,
                "ZOHO_ACCESS_TOKEN": self.access_token,  # REQUIRED
                "ZOHO_ORGANIZATION_ID": self.organization_id,
                "ZOHO_REGION": self.region,
            }

            server_params = StdioServerParameters(
                command="python3",
                args=["-m", server_module, "--stdio"],
                env=env,
            )

        else:
            # Use pip-installed module
            env = {
                "ZOHO_CLIENT_ID": self.client_id,
                "ZOHO_CLIENT_SECRET": self.client_secret,
                "ZOHO_REFRESH_TOKEN": self.refresh_token,
                "ZOHO_ACCESS_TOKEN": self.access_token,  # REQUIRED
                "ZOHO_ORGANIZATION_ID": self.organization_id,
                "ZOHO_REGION": self.region,
            }

            server_params = StdioServerParameters(
                command="python3",
                args=["-m", "zoho_mcp.server", "--stdio"],
                env=env,
            )

        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))

        self.session = await self.exit_stack.enter_async_context(
            ClientSession(stdio_transport[0], stdio_transport[1])
        )

        await self.session.initialize()

    # ------------------------------------------------------
    # Sync wrapper for connection
    # ------------------------------------------------------
    def connect(self):
        """
        Ensure connection is established.
        Thread-safe: submits the _connect coroutine to the background loop.
        """
        if self.session is None:
            future = asyncio.run_coroutine_threadsafe(self._connect(), self._loop)
            try:
                future.result()
            except Exception as e:
                raise RuntimeError(f"Failed to connect to Zoho MCP: {e}")

    # ------------------------------------------------------
    # Call MCP Tool (Async implementation)
    # ------------------------------------------------------
    async def _call_tool(self, tool_name, arguments):
        if self.session is None:
            await self._connect()

        response = await self.session.call_tool(tool_name, arguments)

        # Extract text output
        if hasattr(response, "content") and response.content:
            item = response.content[0]
            if hasattr(item, "text"):
                return item.text

        return str(response)

    # ------------------------------------------------------
    # Sync wrapper for tool call
    # ------------------------------------------------------
    def call_tool(self, tool_name, arguments):
        """
        Call an MCP tool synchronously.
        Thread-safe: submits the _call_tool coroutine to the background loop.
        """
        # Ensure we are connected first
        self.connect()
        
        future = asyncio.run_coroutine_threadsafe(self._call_tool(tool_name, arguments), self._loop)
        try:
            return future.result()
        except Exception as e:
            raise RuntimeError(f"Error calling tool {tool_name}: {e}")

    # ------------------------------------------------------
    # Close session
    # ------------------------------------------------------
    def close(self):
        if self.exit_stack:
            # We need to close the exit stack on the loop
            future = asyncio.run_coroutine_threadsafe(self.exit_stack.aclose(), self._loop)
            try:
                future.result()
            except Exception:
                pass
            self.session = None
            
        # Stop the loop? Usually we keep it running for the life of the application
        # or until explicit shutdown. For now, we leave the thread running.
