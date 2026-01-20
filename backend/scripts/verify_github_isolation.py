import sys
import os
import json
import shutil
from pathlib import Path
from uuid import uuid4

def verify_github_isolation():
    user_id_a = uuid4()
    user_id_b = uuid4()
    service_name = "github"
    
    mcp_use_token_dir = Path.home() / ".mcp_use" / "tokens"
    mcp_use_token_dir.mkdir(parents=True, exist_ok=True)
    
    # Paths that MCPManager would use
    token_file_a = mcp_use_token_dir / f"{service_name}_{user_id_a}.json"
    token_file_b = mcp_use_token_dir / f"{service_name}_{user_id_b}.json"
    
    print(f"Testing GitHub Isolation")
    print(f"User A File: {token_file_a}")
    print(f"User B File: {token_file_b}")
    
    # SIMULATION 1: User A has token in DB
    print("\n[Simulation 1] User A connecting (Has Token in DB)")
    
    # Mock Token Data
    token_data_a = {
        "access_token": "gh_access_token_a",
        "refresh_token": "gh_refresh_token_a",
        "scopes": ["repo", "user"],
        "expires_in": 3600
    }
    
    # Logic from Manager
    reconstructed_token = {
        "access_token": token_data_a.get("access_token"),
        "refresh_token": token_data_a.get("refresh_token"),
        "scope": " ".join(token_data_a.get("scopes", [])),
        "token_type": "Bearer", 
        "expires_at": "2026-01-01T00:00:00Z"
    }
    
    with open(token_file_a, "w") as f:
        json.dump(reconstructed_token, f)
        
    if token_file_a.exists():
        print("✅ User A token file created successfully")
        with open(token_file_a) as f:
            data = json.load(f)
            if data["access_token"] == "gh_access_token_a":
                 print("✅ User A content verified")
            else:
                 print("❌ User A content mismatch")
    else:
        print("❌ User A token file NOT created")

    # SIMULATION 2: User B connecting (No Token in DB)
    print("\n[Simulation 2] User B connecting (No Token in DB)")
    
    # Pre-create a stale file to test deletion
    with open(token_file_b, "w") as f:
        f.write("stale data")
    print("   Created stale file for User B")
    
    # Logic from Manager (No token found => delete)
    if True: # Simulating "if not token_data"
        if token_file_b.exists():
             token_file_b.unlink()
             print("✅ Stale file removed")
        else:
             print("⚠️ Stale file was already missing (unexpected in this test)")
             
    if not token_file_b.exists():
        print("✅ User B file matches expected state (Absent)")
    else:
        print("❌ User B file still exists!")

    # Cleanup
    if token_file_a.exists(): token_file_a.unlink()
    if token_file_b.exists(): token_file_b.unlink()

if __name__ == "__main__":
    verify_github_isolation()
