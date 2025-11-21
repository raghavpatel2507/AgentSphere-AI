# Gmail OAuth Setup Guide

## Prerequisites

1. **Google Cloud Console Setup**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select an existing one
   - Enable the **Gmail API**
   - Create OAuth 2.0 credentials:
     - Application type: **Desktop app**
     - Download the credentials JSON file
     - Save it as `src/configs/gmail_credential.json`

2. **Required Scopes**
   - `https://www.googleapis.com/auth/gmail.modify` (read, send, modify emails)

## Authentication Flow

### Step 1: Run the OAuth Script

```bash
python authenticate_gmail.py
```

### Step 2: Complete Browser Authentication

1. The script will automatically open your default browser
2. You'll see the Google OAuth consent screen
3. Select the Gmail account you want to authenticate
4. Grant the requested permissions
5. The browser will show "Authentication Successful!"

### Step 3: Verification

The script will:
- ✅ Save tokens to `src/configs/gmail_token.json`
- ✅ Display the authenticated email address
- ✅ Confirm setup completion

## Using the Gmail Agent

Once authenticated, you can use the Gmail agent in your application:

```bash
python main.py
```

Example queries:
- "list my unread emails"
- "send an email to john@example.com with subject 'Hello' and message 'Hi there!'"
- "search for emails from alice@example.com"
- "create a draft email to bob@example.com"

## File Structure

```
src/configs/
├── gmail_credential.json  # OAuth client credentials (gitignored)
└── gmail_token.json       # Access & refresh tokens (gitignored)
```

## Troubleshooting

### Error: Missing gmail_credential.json
- Make sure you've downloaded the OAuth credentials from Google Cloud Console
- Save it in the correct location: `src/configs/gmail_credential.json`

### Error: Token expired
- Run `python authenticate_gmail.py` again to refresh the token
- The script will automatically handle token refresh

### Error: Port 8098 already in use
- Close any application using port 8098
- Or modify `REDIRECT_PORT` in `authenticate_gmail.py`

## Security Notes

⚠️ **Important**: Both `gmail_credential.json` and `gmail_token.json` are automatically gitignored. Never commit these files to version control.

## Re-authentication

To switch to a different Gmail account:
1. Delete `src/configs/gmail_token.json`
2. Run `python authenticate_gmail.py` again
3. Authenticate with the new account
