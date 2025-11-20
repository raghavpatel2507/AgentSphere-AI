import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

MCP_URL = "https://api.githubcopilot.com/mcp/x/repos"
TOKEN = os.getenv("GITHUB_MCP_TOKEN")
OWNER = os.getenv("GITHUB_USERNAME")

if not TOKEN:
    raise RuntimeError("Missing GITHUB_MCP_TOKEN")

if not OWNER:
    raise RuntimeError("Missing GITHUB_USERNAME")

BASE_HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "X-MCP-Toolsets": "repos",
}


class GitHubMCPClient:
    def __init__(self):
        self.owner = OWNER   # <-- username available everywhere
        self.session_id = self.initialize_session()

    def initialize_session(self):
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

        return sid

    def call_tool(self, tool_name, arguments):
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
