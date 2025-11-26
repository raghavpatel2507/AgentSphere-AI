import asyncio
import os
import json
import httpx
from dotenv import load_dotenv

load_dotenv()

async def test_github_connection():
    url = "https://api.githubcopilot.com/mcp/x/repos"
    token = os.getenv("GITHUB_TOKEN")
    
    print(f"Token present: {bool(token)}")
    if token:
        print(f"Token length: {len(token)}")
        print(f"Token start: {token[:4]}...")
    
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "agent-sphere-ai/1.0",
        "X-MCP-Toolsets": "repos",
        "Authorization": f"Bearer {token}" if token else None
    }
    
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "clientInfo": {
                "name": "agent-sphere-ai",
                "version": "1.0.0"
            },
            "capabilities": {"tools": {}},
        },
    }
    
    print(f"\nConnecting to {url}")
    print(f"Headers: {json.dumps({k: v if k != 'Authorization' else 'Bearer [REDACTED]' for k,v in headers.items()}, indent=2)}")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload, headers=headers)
            print(f"\nResponse Status: {response.status_code}")
            print(f"Response Headers: {dict(response.headers)}")
            print(f"Response Body: {response.text}")
            response.raise_for_status()
            print("✅ Connection successful!")
        except Exception as e:
            print(f"❌ Connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_github_connection())
