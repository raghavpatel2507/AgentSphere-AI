# Authentication Setup

This folder contains OAuth authentication scripts and setup documentation for connecting to external services.

## Available Authentications

### Gmail

**Documentation**: [GMAIL_SETUP.md](./GMAIL_SETUP.md)  
**Script**: `authenticate_gmail.py`  
**Purpose**: Set up OAuth credentials for Gmail API access

**Quick Start**:
```bash
python authentication/authenticate_gmail.py
```

This will:
- Launch your browser for Google OAuth
- Save credentials to `src/configs/gmail_credential.json`
- Save access/refresh tokens to `src/configs/gmail_token.json`

---

### Zoho Books

**Documentation**: [ZOHO_SETUP.md](./ZOHO_SETUP.md)  
**Script**: `authenticate_zoho.py`  
**Purpose**: Set up OAuth credentials for Zoho Books API access

**Quick Start**:
```bash
python authentication/authenticate_zoho.py
```

This will:
- Launch your browser for Zoho OAuth
- Save credentials to `src/configs/zoho_credential.json`
- Save access/refresh tokens to `src/configs/zoho_token.json`
- Automatically fetch and save your organization ID

## File Structure

```
authentication/
├── README.md                  # This file
├── GMAIL_SETUP.md            # Gmail OAuth setup guide
├── ZOHO_SETUP.md             # Zoho Books OAuth setup guide
├── authenticate_gmail.py     # Gmail OAuth script
└── authenticate_zoho.py      # Zoho Books OAuth script
```

## Configuration Storage

All credentials and tokens are stored in:
```
src/configs/
├── gmail_credential.json     # Gmail OAuth client credentials (gitignored)
├── gmail_token.json          # Gmail access & refresh tokens (gitignored)
├── zoho_credential.json      # Zoho OAuth client credentials (gitignored)
└── zoho_token.json           # Zoho access & refresh tokens (gitignored)
```

⚠️ **Security**: All credential and token files are automatically gitignored. Never commit these to version control.

## Re-authentication

To refresh credentials or switch accounts:
1. Delete the appropriate token file from `src/configs/`
2. Run the authentication script again
3. Complete the OAuth flow in your browser

## Troubleshooting

### Port Already in Use

Each authentication script uses a different port:
- Gmail: `8098`
- Zoho: `8099`

If you receive a "port already in use" error, either close the application using that port or modify the `REDIRECT_PORT` in the respective script.

### Missing Credentials

Ensure you've properly created the credential JSON files from the respective developer consoles:
- **Gmail**: [Google Cloud Console](https://console.cloud.google.com/)
- **Zoho**: [Zoho API Console](https://api-console.zoho.com/)

See the individual setup guides for detailed instructions.
