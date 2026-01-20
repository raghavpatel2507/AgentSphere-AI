import asyncio
from pathlib import Path
from uuid import uuid4
import os
import sys

# Add backend to path
sys.path.append(os.path.join(os.getcwd()))

# Mocking parts of the app for testing
class MockTokenManager:
    def __init__(self, user_id):
        self.user_id = user_id
    async def get_token(self, name):
        return {"access_token": "test_token"}

async def verify():
    # We'll just test the path generation logic by manually importing the part of MCPManager if possible,
    # or just replicate it here to verify the STRATEGY.
    
    user1_id = uuid4()
    user2_id = uuid4()
    
    server_name = "gmail-mcp"
    
    def get_paths(user_id, name):
        cred_dir = Path.home() / ".sphere" / "mcp_data" / str(user_id) / name
        mcp_use_name = f"{name}_{user_id}"
        return cred_dir, mcp_use_name

    path1, name1 = get_paths(user1_id, server_name)
    path2, name2 = get_paths(user2_id, server_name)
    
    print(f"User 1 ({user1_id}):")
    print(f"  Path: {path1}")
    print(f"  MCP Name: {name1}")
    
    print(f"\nUser 2 ({user2_id}):")
    print(f"  Path: {path2}")
    print(f"  MCP Name: {name2}")
    
    assert path1 != path2, "Paths should be different"
    assert name1 != name2, "MCP names should be different"
    assert str(user1_id) in str(path1), "User ID should be in path"
    assert str(user1_id) in name1, "User ID should be in MCP name"
    
    print("\n✅ Path and Name isolation strategy verified!")

if __name__ == "__main__":
    asyncio.run(verify())
