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

BASE_HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "X-MCP-Toolsets": "repos",
}

def initialize_session():
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
    
    return sid

def list_tools(session_id):
    headers = BASE_HEADERS.copy()
    headers["Mcp-Session-Id"] = session_id

    payload = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {},
    }

    resp = requests.post(MCP_URL, headers=headers, json=payload)
    print(json.dumps(resp.json(), indent=2))

if __name__ == "__main__":
    try:
        sid = initialize_session()
        list_tools(sid)
    except Exception as e:
        print(f"Error: {e}")
