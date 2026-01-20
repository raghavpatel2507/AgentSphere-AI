import sys
import os
import json
import shutil
from pathlib import Path
from uuid import uuid4

# Simulate the logic in MCPManager._connect_single verify paths and file content
def verify_google_setup():
    user_id = uuid4()
    service_name = "gmail-mcp"
    
    # Mock data
    token_data = {
        "access_token": "mock_access_token",
        "refresh_token": "mock_refresh_token",
        "scopes": ["https://www.googleapis.com/auth/gmail.readonly"],
        "expires_in": 3600
    }
    
    client_id = "mock_client_id"
    client_secret = "mock_client_secret"
    
    # 1. Determine paths (Logic from Manager)
    cred_dir = Path.home() / ".sphere" / "mcp_data" / str(user_id) / service_name
    
    # 2. Simulate File Writing
    if cred_dir.exists():
        shutil.rmtree(cred_dir)
    cred_dir.mkdir(parents=True, exist_ok=True)
    
    cred_path = cred_dir / "credentials.json"
    tokens_path = cred_dir / "tokens.json"
    
    # Write Credentials
    gcp_secrets = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"]
        }
    }
    with open(cred_path, "w") as f:
        json.dump(gcp_secrets, f)
        
    # Write Tokens
    expiry_date = 1700000000000 # Mock timestamp
    token_json = {
        "access_token": token_data["access_token"],
        "refresh_token": token_data.get("refresh_token"),
        "scope": " ".join(token_data.get("scopes", [])),
        "token_type": "Bearer",
        "expiry_date": expiry_date
    }
    
    with open(tokens_path, "w") as f:
        json.dump(token_json, f)
        
    # Redundant files logic
    token_singular_path = cred_dir / "token.json"
    with open(token_singular_path, "w") as f:
        json.dump(token_json, f)
        
    # 3. Verify Files Exist
    print(f"Checking directory: {cred_dir}")
    if not cred_path.exists():
        print("❌ credentials.json missing")
    else:
        print("✅ credentials.json created")
        
    if not tokens_path.exists():
        print("❌ tokens.json missing")
    else:
        print("✅ tokens.json created")
        
    if not token_singular_path.exists():
        print("❌ token.json missing")
    else:
        print("✅ token.json created")
        
    # 4. Verify Env Vars Logic
    resolved_config = {"env": {}}
    
    # Gmail logic
    resolved_config["env"]["GMAIL_OAUTH_PATH"] = str(cred_path)
    resolved_config["env"]["GMAIL_CREDENTIALS_PATH"] = str(token_singular_path)
    resolved_config["env"]["GMAIL_CREDENTIALS_FILE"] = str(cred_path)
    resolved_config["env"]["GMAIL_TOKEN_FILE"] = str(token_singular_path)
    
    print("\nEnvironment Variables Configuration:")
    print(json.dumps(resolved_config["env"], indent=2))
    
    # Cleanup
    shutil.rmtree(cred_dir.parent)
    print(f"\nCleaned up {cred_dir.parent}")

if __name__ == "__main__":
    verify_google_setup()
