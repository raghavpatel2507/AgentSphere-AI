import os
import json
import requests
from dotenv import load_dotenv

# Load environment variables (.env must contain GITHUB_MCP_TOKEN and GITHUB_USERNAME)
load_dotenv()

MCP_URL = "https://api.githubcopilot.com/mcp/x/repos"
TOKEN = os.getenv("GITHUB_MCP_TOKEN")
OWNER = os.getenv("GITHUB_USERNAME")

if not TOKEN:
    raise RuntimeError("❌ Missing GITHUB_MCP_TOKEN in .env")

if not OWNER:
    raise RuntimeError("❌ Missing GITHUB_USERNAME in .env")

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "X-MCP-Toolsets": "repos",
}


# ---------------------------------------------------------
# 1️⃣ Initialize MCP Session
# ---------------------------------------------------------
def initialize_session():
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "clientInfo": {"name": "demo-mcp-client", "version": "1.0"},
            "capabilities": {"tools": {}},
        },
    }

    resp = requests.post(MCP_URL, headers=headers, json=payload)
    data = resp.json()

    session_id = (
        resp.headers.get("Mcp-Session-Id")
        or resp.headers.get("mcp-session-id")
        or data.get("result", {}).get("sessionId")
    )

    if not session_id:
        raise RuntimeError("❌ Failed to initialize MCP session")

    print(f"✅ Session Started: {session_id}\n")
    return session_id


# ---------------------------------------------------------
# 2️⃣ List Available Tools
# ---------------------------------------------------------
def list_tools(session_id):
    print("🧰 Available MCP Tools:")
    payload = {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}

    hdrs = headers.copy()
    hdrs["Mcp-Session-Id"] = session_id

    resp = requests.post(MCP_URL, headers=hdrs, json=payload)
    data = resp.json()

    tools = data.get("result", {}).get("tools", [])

    for t in tools:
        print(" -", t["name"])

    print()
    return tools


# ---------------------------------------------------------
# 3️⃣ List User Repositories
# ---------------------------------------------------------
def list_repositories(session_id, owner):
    print(f"📦 Fetching Repositories for: {owner}")

    payload = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "search_repositories",
            "arguments": {
                "query": f"{owner} in:owner",
                "sort": "updated",
                "order": "desc",
                "per_page": 20
            },
        },
    }

    hdrs = headers.copy()
    hdrs["Mcp-Session-Id"] = session_id
    resp = requests.post(MCP_URL, headers=hdrs, json=payload)
    data = resp.json()

    if data.get("result", {}).get("isError"):
        print("❌ MCP Error:", data["result"]["content"][0]["text"])
        return

    # MCP returns JSON inside a string → parse it
    raw = data["result"]["content"][0]["text"]
    repos = json.loads(raw)

    print(f"✅ {len(repos.get('items', []))} repos found:\n")

    for r in repos["items"]:
        print(f"📁 {r['full_name']}")
        print(f"   → {r['html_url']}")
        print(f"   📝 {r.get('description', '')}")
        print()

    return repos


# ---------------------------------------------------------
# ▶️ RUN DEMO
# ---------------------------------------------------------
if __name__ == "__main__":
    session_id = initialize_session()
    list_tools(session_id)
    list_repositories(session_id, OWNER)
