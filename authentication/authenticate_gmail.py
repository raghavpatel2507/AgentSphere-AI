import json
import os
import sys
import webbrowser
import time
import threading
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------
CREDENTIALS_FILE = "src/configs/gmail_credential.json"
TOKEN_FILE = "src/configs/gmail_token.json"
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

    def log_message(self, *args):
        return


def start_server():
    global server_instance
    server_instance = HTTPServer(("localhost", REDIRECT_PORT), OAuthCallbackHandler)
    server_instance.serve_forever()


# ---------------------------------------------------------
# Utilities
# ---------------------------------------------------------
def load_client_credentials():
    if not os.path.exists(CREDENTIALS_FILE):
        print("❌ Missing OAuth credentials file.")
        sys.exit(1)

    with open(CREDENTIALS_FILE, "r") as f:
        return json.load(f)


def save_token_data(token):
    with open(TOKEN_FILE, "w") as f:
        json.dump(token, f, indent=2)

    print(f"\n✅ Tokens saved to {TOKEN_FILE}")
    print("\n📌 Granted scopes (from Google):")
    for s in token["scopes"]:
        print(f"   • {s}")


def get_email_from_token(token):
    creds = Credentials(
        token=token["access_token"],
        refresh_token=token.get("refresh_token"),
        token_uri=token["token_uri"],
        client_id=token["client_id"],
        client_secret=token["client_secret"],
        scopes=token["scopes"]
    )

    try:
        service = build("gmail", "v1", credentials=creds)
        profile = service.users().getProfile(userId="me").execute()
        return profile.get("emailAddress", "Unknown")
    except Exception as e:
        return f"Error fetching email: {e}"


# ---------------------------------------------------------
# Manual Token Exchange (NO SCOPE VALIDATION)
# ---------------------------------------------------------
def exchange_code_for_token(auth_code, client_cfg):
    token_url = client_cfg["installed"]["token_uri"]

    data = {
        "code": auth_code,
        "client_id": client_cfg["installed"]["client_id"],
        "client_secret": client_cfg["installed"]["client_secret"],
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code"
    }

    response = requests.post(token_url, data=data)
    if response.status_code != 200:
        print("\n❌ Token Exchange Failed")
        print(response.text)
        sys.exit(1)

    token_json = response.json()

    # Build normalized token structure
    return {
        "access_token": token_json["access_token"],
        "refresh_token": token_json.get("refresh_token"),
        "token_uri": token_url,
        "client_id": client_cfg["installed"]["client_id"],
        "client_secret": client_cfg["installed"]["client_secret"],
        "scopes": token_json["scope"].split(" ")
    }


# ---------------------------------------------------------
# Main Flow
# ---------------------------------------------------------
def main():
    print("\n==============================")
    print(" Gmail OAuth Login")
    print("==============================\n")

    client_cfg = load_client_credentials()

    # Start callback server
    thread = threading.Thread(target=start_server, daemon=True)
    thread.start()

    # Build authorization URL manually
    params = {
        "response_type": "code",
        "client_id": client_cfg["installed"]["client_id"],
        "redirect_uri": REDIRECT_URI,
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
    }
    import urllib.parse
    auth_url = (
        client_cfg["installed"]["auth_uri"] + "?" +
        urllib.parse.urlencode(params)
    )

    print("Open the following link:\n")
    print(auth_url + "\n")

    try:
        webbrowser.open(auth_url)
    except:
        pass

    print("Waiting for authentication...")

    while auth_code is None:
        time.sleep(1)

    print("\n✨ Authorization Code Received!")

    # 🔥 Manual token exchange (no scope mismatch error)
    token = exchange_code_for_token(auth_code, client_cfg)

    save_token_data(token)

    print("\nFetching user email...")
    email = get_email_from_token(token)
    print(f"✅ Authenticated as: {email}")

    if server_instance:
        server_instance.shutdown()

    print("\n🎉 Gmail OAuth Setup Complete")
    sys.exit(0)


if __name__ == "__main__":
    main()
