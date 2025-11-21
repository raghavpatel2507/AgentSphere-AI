import requests
import json


CREDENTIALS_FILE = "src/configs/zoho_credential.json"
TOKEN_FILE = "src/configs/zoho_token.json"


def load_tokens():
    with open(TOKEN_FILE, "r") as f:
        return json.load(f)


def load_credentials():
    with open(CREDENTIALS_FILE, "r") as f:
        return json.load(f)


def get_customers(access_token, org_id, region):
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
    url = f"https://{api_domain}/api/v3/contacts"

    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}"
    }

    customers = []
    page = 1
    while True:
        params = {"organization_id": org_id, "type": "customer", "page": page}
        response = requests.get(url, headers=headers, params=params)
        data = response.json()

        if response.status_code != 200 or "contacts" not in data:
            break

        customers.extend(data["contacts"])

        if len(data["contacts"]) < 200:
            break

        page += 1

    return customers


def main():
    tokens = load_tokens()
    creds = load_credentials()

    access_token = tokens["access_token"]
    org_id = creds["organization_id"]
    region = creds.get("region", "US")

    customers = get_customers(access_token, org_id, region)

    with open("zoho_customers.json", "w") as f:
        json.dump(customers, f, indent=2)

    print(f"Fetched {len(customers)} customers")


if __name__ == "__main__":
    main()
