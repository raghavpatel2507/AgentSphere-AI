import os
import json
import re
import logging
import httpx
from typing import List, Dict, Any, Optional
from .base import MCPHandler
from mcp.types import Tool

logger = logging.getLogger(__name__)

class HttpMCPHandler(MCPHandler):
    """
    Simple and stable HTTP MCP handler.
    Works with:
      ✔ Figma MCP (requires PAT)
      ✔ GitHub Copilot MCP
      ✔ Zoho MCP
      ✔ Any standard MCP server
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.url = config.get("url")
        self.session_id: Optional[str] = None
        self.client: Optional[httpx.AsyncClient] = None

        # Base headers
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "User-Agent": "agent-sphere-ai/1.0"
        }

        # ---- Load env vars defined in "env" block ----
        env_block = config.get("env", {})
        for key, val in env_block.items():
            if isinstance(val, str) and val.startswith("${") and val.endswith("}"):
                env_name = val[2:-1]
                resolved = os.getenv(env_name)
                if resolved:
                    self.headers[key] = resolved

        # ---- Load custom headers and substitute ${VAR} ----
        custom_headers = config.get("headers", {})
        for k, v in custom_headers.items():
            if isinstance(v, str):
                matches = re.findall(r"\$\{([A-Za-z0-9_]+)\}", v)
                for var in matches:
                    env_value = os.getenv(var, "")
                    v = v.replace(f"${{{var}}}", env_value)
            self.headers[k] = v

    # ------------------------------------------------------
    # CONNECT (INITIALIZE)
    # ------------------------------------------------------
    async def connect(self):
        if not self.url:
            raise ValueError("URL is required for HTTP MCP server")

        self.client = httpx.AsyncClient(headers=self.headers, timeout=30)

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "clientInfo": {"name": "agent-sphere-ai", "version": "1.0"},
                "capabilities": {"tools": {}},
            }
        }

        response = await self.client.post(self.url, json=payload)

        if response.status_code == 401:
            print(f"❌ Unauthorized connecting to {self.url}")
            print("Headers used:", self.headers)
            return False

        response.raise_for_status()
        data = response.json()

        self.session_id = (
            response.headers.get("Mcp-Session-Id")
            or data.get("result", {}).get("sessionId")
        )

        print(f"✅ Connected to MCP server with session: {self.session_id}")
        return True

    # ------------------------------------------------------
    # DISCONNECT
    # ------------------------------------------------------
    async def disconnect(self):
        if self.client:
            await self.client.aclose()
        self.client = None
        self.session_id = None

    # ------------------------------------------------------
    # LIST TOOLS
    # ------------------------------------------------------
    async def list_tools(self) -> List[Tool]:
        if not self.client:
            raise RuntimeError("Not connected")

        headers = self.headers.copy()
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id

        payload = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }

        response = await self.client.post(self.url, json=payload, headers=headers)

        if response.status_code == 401:
            raise RuntimeError(f"401 Unauthorized listing tools @ {self.url}")

        response.raise_for_status()
        data = response.json()

        tools_raw = data.get("result", {}).get("tools", [])
        tools: List[Tool] = []

        for t in tools_raw:
            tools.append(Tool(
                name=t.get("name"),
                description=t.get("description"),
                inputSchema=t.get("inputSchema", {"type": "object"})
            ))

        return tools

    # ------------------------------------------------------
    # CALL TOOL
    # ------------------------------------------------------
    async def call_tool(self, tool_name: str, arguments: dict) -> Any:
        if not self.client:
            raise RuntimeError("Not connected")

        headers = self.headers.copy()
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id

        payload = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }

        try:
            response = await self.client.post(self.url, json=payload, headers=headers)

            if response.status_code != 200:
                return f"HTTP {response.status_code}: {response.text}"

            data = response.json()

            if "error" in data:
                return f"Error: {data['error']}"

            return data.get("result", {})

        except Exception as e:
            logger.error(f"Tool call failed: {e}")
            return f"Error: {str(e)}"
