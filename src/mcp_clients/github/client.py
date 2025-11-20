"""
GitHub MCP Client
=================
Thread-safe client for GitHub Copilot MCP API.
"""

import os
import requests
import json
import threading
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv

load_dotenv()

MCP_URL = "https://api.githubcopilot.com/mcp/x/repos"
TOKEN = os.getenv("GITHUB_MCP_TOKEN")
OWNER = os.getenv("GITHUB_USERNAME")

if not TOKEN:
    raise RuntimeError("Missing GITHUB_MCP_TOKEN in .env file")

if not OWNER:
    raise RuntimeError("Missing GITHUB_USERNAME in .env file")

BASE_HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "X-MCP-Toolsets": "repos",
}


class GithubMCPClient:
    """Singleton client for GitHub Copilot MCP API"""
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self.owner = OWNER
            self.session_id: Optional[str] = None
            self._lock = threading.Lock()
            self.__class__._initialized = True
    
    def _ensure_session(self):
        """Initialize session if not already done"""
        if self.session_id is not None:
            return
            
        with self._lock:
            if self.session_id is not None:
                return
                
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "clientInfo": {
                        "name": "agentic-ai-client",
                        "version": "1.0.0"
                    },
                    "capabilities": {"tools": {}},
                },
            }

            resp = requests.post(MCP_URL, headers=BASE_HEADERS, json=payload)
            data = resp.json()

            sid = (
                resp.headers.get("Mcp-Session-Id") or
                resp.headers.get("mcp-session-id") or
                data.get("result", {}).get("sessionId")
            )

            if not sid:
                raise RuntimeError("Failed to initialize GitHub MCP session")

            self.session_id = sid

    def call_tool_sync(self, tool_name: str, arguments: dict):
        """
        Synchronous tool call.
        Automatically injects 'owner' parameter if not provided.
        """
        self._ensure_session()
        
        # Inject owner if not present in arguments
        if "owner" not in arguments and self.owner:
            arguments = {**arguments, "owner": self.owner}
        
        headers = BASE_HEADERS.copy()
        headers["Mcp-Session-Id"] = self.session_id

        payload = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
            },
        }

        resp = requests.post(MCP_URL, headers=headers, json=payload)
        data = resp.json()

        if data.get("result", {}).get("isError"):
            return {
                "error": True,
                "message": data["result"]["content"][0]["text"]
            }

        try:
            raw = data["result"]["content"][0]["text"]
            return json.loads(raw)
        except:
            return data

    def list_tools_sync(self) -> List[Any]:
        """
        List available GitHub tools.
        Returns a list of mock tool objects compatible with the dynamic loader.
        """
        self._ensure_session()
        
        headers = BASE_HEADERS.copy()
        headers["Mcp-Session-Id"] = self.session_id

        payload = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/list",
            "params": {},
        }

        resp = requests.post(MCP_URL, headers=headers, json=payload)
        data = resp.json()
        
        # Extract tools from response
        tools_data = data.get("result", {}).get("tools", [])
        
        # Convert to mock MCP tool format
        mock_tools = []
        for tool in tools_data:
            # Get the input schema and inject owner parameter if needed
            input_schema = tool.get('inputSchema', {"type": "object", "properties": {}, "required": []})
            
            # Add owner parameter to schema if not present
            if "properties" in input_schema and "owner" not in input_schema["properties"]:
                input_schema["properties"]["owner"] = {
                    "type": "string",
                    "description": f"Repository owner (default: {self.owner})",
                    "default": self.owner
                }
            
            mock_tool = type('MockTool', (), {
                'name': tool.get('name', ''),
                'description': tool.get('description', ''),
                'inputSchema': input_schema
            })()
            mock_tools.append(mock_tool)
        
        return mock_tools

    def connect_sync(self):
        """Connect to GitHub MCP (initialize session)"""
        self._ensure_session()
        
    def close_sync(self):
        """Close connection (no-op for GitHub MCP)"""
        pass
