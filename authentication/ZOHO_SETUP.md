# Zoho Books OAuth Setup Guide

## Prerequisites

1. **Zoho Developer Console Setup**
   - Go to [Zoho API Console](https://api-console.zoho.com/)
   - Create a new Self Client application
   - Application type: **Self Client**
   - Note down your Client ID and Client Secret
   - Set redirect URI to: `http://localhost:8099/callback`
   - Create a JSON file at `src/configs/zoho_credential.json` with:
     ```json
     {
       "client_id": "YOUR_CLIENT_ID",
       "client_secret": "YOUR_CLIENT_SECRET",
       "region": "US"
     }
     ```

2. **Required Scopes**
   - `ZohoBooks.fullaccess.all` (full access to Zoho Books)

3. **Region Configuration**
   - Supported regions: `US`, `EU`, `IN`, `AU`, `JP`, `UK`, `CA`
   - Update the `region` field in `zoho_credential.json` based on your account

## Authentication Flow

### Step 1: Run the OAuth Script

```bash
python authentication/authenticate_zoho.py
```

### Step 2: Complete Browser Authentication

1. The script will automatically open your default browser
2. You'll see the Zoho OAuth consent screen
3. Select the Zoho Books account you want to authenticate
4. Grant the requested permissions
5. The browser will show "Authentication Successful!"

### Step 3: Verification

The script will:
- ✅ Save tokens to `src/configs/zoho_token.json`
- ✅ Fetch your organization ID automatically
- ✅ Update `zoho_credential.json` with organization details
- ✅ Confirm setup completion

## Using the Zoho Books Agent

Once authenticated, you can use the Zoho Books agent in your application:

```bash
python main.py
```

Example queries:
- "list my contacts in Zoho Books"
- "create a new invoice for customer ABC Corp"
- "show me all unpaid invoices"
- "get my account balance"

## File Structure

```
src/configs/
├── zoho_credential.json  # OAuth client credentials (gitignored)
└── zoho_token.json        # Access & refresh tokens (gitignored)
```

## Troubleshooting

### Error: Missing zoho_credential.json
- Make sure you've created the credential file from Zoho API Console
- Save it in the correct location: `src/configs/zoho_credential.json`
- Ensure it contains `client_id`, `client_secret`, and `region`

### Error: Token expired
- Run `python authentication/authenticate_zoho.py` again to refresh the token
- The script will automatically handle token refresh

### Error: Port 8099 already in use
- Close any application using port 8099
- Or modify `REDIRECT_PORT` in `authentication/authenticate_zoho.py`

### Error: Organization ID not found
- Ensure you have at least one organization in your Zoho Books account
- The script automatically selects the first organization
- You can manually set `organization_id` in `zoho_credential.json`

### Error: Wrong region
- Verify your Zoho account's region (US/EU/IN/AU/JP/UK/CA)
- Update the `region` field in `zoho_credential.json`
- Re-run the authentication script

## Security Notes

⚠️ **Important**: Both `zoho_credential.json` and `zoho_token.json` are automatically gitignored. Never commit these files to version control.

## Re-authentication

To switch to a different Zoho Books account:
1. Delete `src/configs/zoho_token.json`
2. Run `python authentication/authenticate_zoho.py` again
3. Authenticate with the new account
