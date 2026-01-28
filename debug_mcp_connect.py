
import asyncio
import sys
import os

# Ensure we can import from backend
sys.path.append(os.getcwd())

from mcp_use.client import MCPClient

async def test_zoho_connection():
    # Simulate the config payload that Frontend sends
    # Note: Authorization header should NOT contain "Bearer " if token is empty
    # We will test Scenario A: URL Only
    
    # FILL IN YOUR REAL URL HERE FOR TEST OR USE DUMMY
    # I will use a dummy one that likely fails 404 but shouldn't trigger Auth
    url = "https://example.com/mcp?key=123" 
    
    config = {
        "type": "httpx",
        "url": url,
        "headers": {
            "Content-Type": "application/json"
        }
    }
    
    print(f"Testing Connection to {url} with config: {config}")
    
    client = MCPClient()
    try:
        session = await client.create_session("test_zoho", config)
        print("✅ Connection Successful!")
        await session.close()
    except Exception as e:
        print(f"❌ Connection Failed: {e}")
        # Check if error message suggests Auth Trigger
        if "authorize" in str(e).lower() or "oauth" in str(e).lower():
            print("⚠️  SUSPICION CONFIRMED: Auth flow triggered by error.")

if __name__ == "__main__":
    asyncio.run(test_zoho_connection())
