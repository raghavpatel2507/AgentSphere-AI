import json
import os
import sys
import webbrowser
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

# Configuration
CREDENTIALS_FILE = "../src/configs/gmail_credential.json"
TOKEN_FILE = "../src/configs/gmail_token.json"
REDIRECT_PORT = 8098
REDIRECT_URI = f"http://localhost:{REDIRECT_PORT}/callback"
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

auth_code = None
server_instance = None


# ---------------------------------------------------------
# Callback Server
# ---------------------------------------------------------
class OAuthCallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code

        query = parse_qs(urlparse(self.path).query)
        if "code" in query:
            auth_code = query["code"][0]

            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"""
                <h1 style='color:green;text-align:center;'>Authentication Successful!</h1>
                <p style='text-align:center;'>You may close this window.</p>
            """)
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Authentication failed")

    def log_message(self, format, *args):
        pass


def start_server():
    global server_instance
    server_instance = HTTPServer(("localhost", REDIRECT_PORT), OAuthCallbackHandler)
    server_instance.serve_forever()


# ---------------------------------------------------------
# Utility Functions
# ---------------------------------------------------------
def get_credentials():
    if not os.path.exists(CREDENTIALS_FILE):
        print(f"❌ Missing {CREDENTIALS_FILE}")
        print("\nPlease create a Gmail OAuth credential file:")
        print("1. Go to https://console.cloud.google.com/")
        print("2. Create a new project or select an existing one")
        print("3. Enable Gmail API")
        print("4. Create OAuth 2.0 credentials (Desktop app)")
        print(f"5. Download and save as {CREDENTIALS_FILE}")
        sys.exit(1)
    with open(CREDENTIALS_FILE, "r") as f:
        return json.load(f)


def save_token(credentials):
    """Save the credentials to token file"""
    token_data = {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }
    with open(TOKEN_FILE, "w") as f:
        json.dump(token_data, f, indent=2)
    print(f"\n✅ Tokens saved to {TOKEN_FILE}")


def get_user_email(credentials):
    """Fetch the authenticated user's email address"""
    try:
        service = build('gmail', 'v1', credentials=credentials)
        profile = service.users().getProfile(userId='me').execute()
        return profile.get('emailAddress', 'Unknown')
    except Exception as error:
        print(f"⚠ Could not fetch user email: {error}")
        return "Unknown"


# ---------------------------------------------------------
# Main OAuth Logic
# ---------------------------------------------------------
def main():
    print("\n==============================")
    print(" Gmail OAuth Login")
    print("==============================\n")

    creds = get_credentials()

    # Launch OAuth Callback Server
    thread = threading.Thread(target=start_server, daemon=True)
    thread.start()

    # Create OAuth flow
    flow = Flow.from_client_config(
        creds,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )

    # Generate authorization URL
    auth_url, _ = flow.authorization_url(
        access_type='offline',
        prompt='consent',
        include_granted_scopes='true'
    )

    print("Open URL in browser:\n")
    print(auth_url + "\n")

    try:
        webbrowser.open(auth_url)
    except:
        pass

    print("Waiting for login...")

    while auth_code is None:
        time.sleep(1)

    print("\n✨ Authorization Code Received!")

    # Exchange code for tokens
    try:
        flow.fetch_token(code=auth_code)
        credentials = flow.credentials
        
        # Save tokens
        save_token(credentials)

        # Fetch user email
        print("\nFetching user email...")
        user_email = get_user_email(credentials)
        print(f"✅ Authenticated as: {user_email}")

    except Exception as e:
        print(f"\n❌ Failed to exchange code for tokens: {e}")
        if server_instance:
            server_instance.shutdown()
        sys.exit(1)

    # Shutdown server
    if server_instance:
        server_instance.shutdown()

    print("\n🎉 Gmail OAuth Setup Complete!")
    print(f"\nYou can now use the Gmail agent with account: {user_email}")
    
    # Exit cleanly
    sys.exit(0)


if __name__ == "__main__":
    main()
