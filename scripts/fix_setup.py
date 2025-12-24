import os
import sys
from cryptography.fernet import Fernet
import json

def fix_setup():
    print("--- AgentSphere-AI Setup Fixer ---")
    
    # 1. Check ENCRYPTION_KEY
    env_path = ".env"
    has_key = False
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except:
             with open(env_path, "r") as f:
                lines = f.readlines()
        
        for line in lines:
            if line.startswith("ENCRYPTION_KEY="):
                key = line.split("=", 1)[1].strip().strip("'").strip('"')
                if key:
                    print(f"DEBUG: Key found: '{key}' (Length: {len(key)})")
                    try:
                        from cryptography.fernet import Fernet
                        Fernet(key.encode())
                        print("Key is valid Fernet.")
                        has_key = True
                    except Exception as e:
                        print(f"Key is INVALID: {e}")
    
    if not has_key:
        new_key = Fernet.generate_key().decode()
        print(f"\n💡 ACTION REQUIRED: Add this valid key to your .env file:")
        print(f"\nACTION REQUIRED: Add this valid key to your .env file:")
        print(f"ENCRYPTION_KEY={new_key}")
        print("Note: Changing the key will make previously saved encrypted data (like app tokens) unreadable.")

    # 2. Check npm / npx
    print("\nChecking npm/npx status...")
    import subprocess
    try:
        result = subprocess.run(["npx", "-v"], capture_output=True, text=True, shell=True)
        print(f"npx version: {result.stdout.strip()}")
        
        # Test a public package download
        print("Testing public package access...")
        test_run = subprocess.run(["npx", "-y", "@modelcontextprotocol/server-arxiv", "--help"], 
                                 capture_output=True, text=True, shell=True, timeout=10)
        if "expired or revoked" in test_run.stderr:
            print("\n❌ npm ERROR detected: 'Access token expired or revoked'")
            print("💡 ACTION REQUIRED: Run the following command in your terminal to fix npm:")
            print("   npm logout")
            print("   (Or delete your ~/.npmrc file if you don't use it for anything else)")
        elif test_run.returncode == 0 or "Usage" in test_run.stdout or "Usage" in test_run.stderr:
            print("✅ npx package access is working.")
        else:
            print(f"⚠️ npx test returned status {test_run.returncode}. It might still be working.")
    except Exception as e:
        print(f"❌ Error checking npx: {e}")

    print("\n----------------------------")
    print("Done! Apply the actions above and restart your App.")

if __name__ == "__main__":
    fix_setup()
