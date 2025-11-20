import json
import os
import sys
import webbrowser
import time
import threading
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Configuration
CREDENTIALS_FILE = "src/Zoho_MCP/credentials.json"
TOKEN_FILE = "src/Zoho_MCP/token.json"
REDIRECT_PORT = 8099
REDIRECT_URI = f"http://localhost:{REDIRECT_PORT}/callback"
SCOPES = "ZohoBooks.fullaccess.all"

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
        print(f"Missing {CREDENTIALS_FILE}")
        sys.exit(1)
    with open(CREDENTIALS_FILE, "r") as f:
        return json.load(f)


def save_tokens(access, refresh):
    data = {
        "access_token": access,
        "refresh_token": refresh
    }
    with open(TOKEN_FILE, "w") as f:
        json.dump(data, f, indent=2)
    print(f"\n✅ Tokens saved to {TOKEN_FILE}")


def update_credentials_with_org(org_id, region):
    with open(CREDENTIALS_FILE, "r") as f:
        creds = json.load(f)

    creds["organization_id"] = org_id
    creds["region"] = region

    with open(CREDENTIALS_FILE, "w") as f:
        json.dump(creds, f, indent=2)

    print(f"✅ Organization ID updated in credentials.json")


def get_organization_id(access_token, region):
    domain_map = {
        "US": "books.zoho.com",
        "EU": "books.zoho.eu",
        "IN": "books.zoho.in",
        "AU": "books.zoho.com.au",
        "JP": "books.zoho.jp",
        "UK": "books.zoho.uk",
        "CA": "books.zoho.ca",
    }

    api_domain = domain_map.get(region, "books.zoho.com")
    url = f"https://{api_domain}/api/v3/organizations"

    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}"
    }

    r = requests.get(url, headers=headers)
    data = r.json()

    if data.get("code") == 0 and data.get("organizations"):
        org = data["organizations"][0]
        return org["organization_id"], org["name"]

    return None, None


# ---------------------------------------------------------
# Main OAuth Logic
# ---------------------------------------------------------
def main():
    print("\n==============================")
    print(" Zoho Books OAuth Login")
    print("==============================\n")

    creds = get_credentials()
    client_id = creds["client_id"]
    client_secret = creds["client_secret"]
    region = creds.get("region", "US")

    auth_domain_map = {
        "US": "accounts.zoho.com",
        "EU": "accounts.zoho.eu",
        "IN": "accounts.zoho.in",
        "AU": "accounts.zoho.com.au",
        "JP": "accounts.zoho.jp",
        "UK": "accounts.zoho.uk",
        "CA": "accounts.zoho.ca",
    }
    auth_domain = auth_domain_map.get(region, "accounts.zoho.com")

    # Launch OAuth Callback Server
    thread = threading.Thread(target=start_server, daemon=True)
    thread.start()

    # Auth URL
    auth_url = (
        f"https://{auth_domain}/oauth/v2/auth?"
        f"scope={SCOPES}&"
        f"client_id={client_id}&"
        f"response_type=code&"
        f"access_type=offline&"
        f"prompt=consent&"
        f"redirect_uri={REDIRECT_URI}"
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

    # Exchange Code for Tokens
    token_url = f"https://{auth_domain}/oauth/v2/token"
    data = {
        "code": auth_code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code"
    }

    response = requests.post(token_url, data=data)
    token_data = response.json()

    if "refresh_token" not in token_data:
        print("\n❌ Failed to get refresh token")
        print(token_data)
        return

    refresh_token = token_data["refresh_token"]
    access_token = token_data["access_token"]

    save_tokens(access_token, refresh_token)

    # Fetch Organization ID
    print("\nFetching organization details...")

    org_id, org_name = get_organization_id(access_token, region)
    if org_id:
        print(f"Organization Found: {org_name} ({org_id})")
        update_credentials_with_org(org_id, region)
    else:
        print("⚠ Could not fetch organization ID")

    if server_instance:
        server_instance.shutdown()

    print("\n🎉 Setup Complete!")


if __name__ == "__main__":
    main()
