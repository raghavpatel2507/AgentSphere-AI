"""
Gmail OAuth Authentication Helper
==================================
Run this ONCE to authenticate your Gmail account.
After this, token.json will be saved and reused automatically.
"""

import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# Gmail API scope
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

# Paths
CREDENTIALS_FILE = "/home/logicrays/Desktop/RAGHAV/AgentSphere-AI/src/Gmail_MCP/credential.json"
TOKEN_FILE = "/home/logicrays/Desktop/RAGHAV/AgentSphere-AI/src/Gmail_MCP/token.json"

def authenticate():
    """
    Authenticate with Gmail and save token
    """
    print("=" * 70)
    print("Gmail Authentication")
    print("=" * 70)
    print()
    
    # Check if token already exists
    if os.path.exists(TOKEN_FILE):
        print(f"✅ Token already exists: {TOKEN_FILE}")
        print()
        response = input("Do you want to re-authenticate? (y/n): ")
        if response.lower() != 'y':
            print("Using existing token.")
            return True
    
    print("Starting OAuth flow...")
    print()
    print("📋 What will happen:")
    print("1. A browser will open (or you'll get a URL)")
    print("2. Sign in to YOUR Gmail account")
    print("3. Click 'Allow' to grant permissions")
    print("4. Token will be saved for future use")
    print()
    
    try:
        # Create OAuth flow
        flow = InstalledAppFlow.from_client_secrets_file(
            CREDENTIALS_FILE, 
            SCOPES
        )
        
        # Run the authentication flow
        # This will try to open browser, or print URL if browser unavailable
        creds = flow.run_local_server(port=0)
        
        # Save the credentials
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
        
        print()
        print("=" * 70)
        print("✅ SUCCESS! Authentication complete!")
        print("=" * 70)
        print()
        print(f"Token saved to: {TOKEN_FILE}")
        print()
        print("You can now use Gmail tools in your agent!")
        print("Just run: python main.py")
        print()
        
        return True
        
    except Exception as e:
        print(f"\n❌ Authentication failed: {e}")
        print()
        print("💡 Troubleshooting:")
        print("1. Make sure credential.json is valid")
        print("2. If browser doesn't open, copy the URL and open manually")
        print("3. Make sure you're using the correct Google account")
        print()
        return False


if __name__ == "__main__":
    print()
    print("This will authenticate your Gmail account for the agent.")
    print()
    input("Press Enter to continue...")
    print()
    
    success = authenticate()
    
    if not success:
        print("Please try again or check your credentials.")
