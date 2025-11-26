"""
YouTube Authentication Setup Script
====================================
This script sets up the credentials for the YouTube MCP server.
It copies the credentials to the server directory and runs authentication.
"""

import os
import shutil
import sys

# Paths
YOUTUBE_SERVER_DIR = "src/mcp_servers/youtube-mcp-server"
CREDENTIALS_SOURCE = "src/configs/youtube_credential.json"
TOKEN_SOURCE = "src/configs/youtube_token.pickle"
CREDENTIALS_DEST = os.path.join(YOUTUBE_SERVER_DIR, "credentials.json")
TOKEN_DEST = os.path.join(YOUTUBE_SERVER_DIR, "token.pickle")


def main():
    print("=" * 60)
    print("🎥 YouTube MCP Setup")
    print("=" * 60)
    print()
    
    # Check if credentials file exists
    if not os.path.exists(CREDENTIALS_SOURCE):
        print(f"❌ Error: Credentials file not found!")
        print(f"📍 Expected location: {CREDENTIALS_SOURCE}")
        print(f"\n📖 Please follow these steps:")
        print(f"   1. Go to https://console.cloud.google.com")
        print(f"   2. Create a new project or select an existing one")
        print(f"   3. Enable YouTube Data API v3")
        print(f"   4. Create OAuth 2.0 credentials (Desktop app)")
        print(f"   5. Download the credentials and save as:")
        print(f"      {CREDENTIALS_SOURCE}")
        print(f"\n📚 See authentication/YOUTUBE_SETUP.md for detailed instructions")
        return False
    
    # Copy credentials to server directory
    print(f"📂 Copying credentials to server directory...")
    try:
        shutil.copy2(CREDENTIALS_SOURCE, CREDENTIALS_DEST)
        print(f"✅ Credentials copied to {CREDENTIALS_DEST}")
    except Exception as e:
        print(f"❌ Error copying credentials: {e}")
        return False
    
    # Check if token already exists in auth directory
    if os.path.exists(TOKEN_SOURCE):
        print(f"📂 Found existing token, copying to server directory...")
        try:
            shutil.copy2(TOKEN_SOURCE, TOKEN_DEST)
            print(f"✅ Token copied to {TOKEN_DEST}")
            print(f"\n✅ YouTube MCP is ready to use!")
            return True
        except Exception as e:
            print(f"⚠️  Warning: Could not copy token: {e}")
    
    
    # Run authentication directly
    print(f"\n🔐 Starting OAuth 2.0 authentication flow...")
    print(f"📖 A browser window will open for authentication")
    print()
    
    try:
        # Import required libraries
        import pickle
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        
        # YouTube API scopes
        SCOPES = [
            'https://www.googleapis.com/auth/youtube.readonly',
            'https://www.googleapis.com/auth/youtube.force-ssl'
        ]
        
        creds = None
        
        # Check if token already exists
        if os.path.exists(TOKEN_SOURCE):
            with open(TOKEN_SOURCE, 'rb') as token:
                creds = pickle.load(token)
        
        # If credentials are invalid or don't exist, authenticate
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                print("🔄 Refreshing expired credentials...")
                creds.refresh(Request())
            else:
                print(f"🔐 Starting OAuth flow...")
                flow = InstalledAppFlow.from_client_secrets_file(
                    CREDENTIALS_SOURCE, SCOPES
                )
                creds = flow.run_local_server(port=0)
            
            # Save credentials
            print(f"💾 Saving credentials to: {TOKEN_SOURCE}")
            with open(TOKEN_SOURCE, 'wb') as token:
                pickle.dump(creds, token)
        
        # Test the credentials
        print(f"\n🧪 Testing YouTube API connection...")
        youtube = build('youtube', 'v3', credentials=creds)
        
        # Simple test: get channel info
        request = youtube.channels().list(
            part='snippet,statistics',
            mine=True
        )
        response = request.execute()
        
        print(f"✅ YouTube API authentication successful!")
        
        if 'items' in response and len(response['items']) > 0:
            channel = response['items'][0]
            print(f"\n📺 Authenticated Channel:")
            print(f"   Name: {channel['snippet']['title']}")
            print(f"   Subscribers: {channel['statistics'].get('subscriberCount', 'N/A')}")
        
        # Copy token to server directory
        if os.path.exists(TOKEN_SOURCE):
            shutil.copy2(TOKEN_SOURCE, TOKEN_DEST)
            print(f"\n✅ Token copied to server directory")
        
        print(f"\n✅ YouTube MCP setup completed successfully!")
        print(f"\n💡 Next steps:")
        print(f"   1. YouTube MCP is already enabled in mcp_config.json")
        print(f"   2. Run: python main.py")
        print(f"   3. Try: 'Search for Python tutorial videos'")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error during setup: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    print("\n" + "=" * 60)
    if success:
        print("✅ Setup completed successfully!")
    else:
        print("❌ Setup failed. Please check the errors above.")
    print("=" * 60)
    sys.exit(0 if success else 1)
