# YouTube MCP Server Setup Guide

## Overview
This guide will help you set up the YouTube MCP server for AgentSphere-AI. You'll need to create a Google Cloud project and obtain YouTube Data API v3 credentials.

## Prerequisites
- Google Account
- Access to Google Cloud Console

## Step-by-Step Setup

### 1. Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Click on the project dropdown at the top
3. Click **"New Project"**
4. Enter a project name (e.g., "AgentSphere YouTube MCP")
5. Click **"Create"**

### 2. Enable YouTube Data API v3

1. In the Google Cloud Console, select your project
2. Go to **"APIs & Services"** > **"Library"**
3. Search for **"YouTube Data API v3"**
4. Click on it and click **"Enable"**

### 3. Create OAuth 2.0 Credentials

1. Go to **"APIs & Services"** > **"Credentials"**
2. Click **"Create Credentials"** > **"OAuth client ID"**
3. If prompted, configure the OAuth consent screen:
   - User Type: **External**
   - App name: **"AgentSphere YouTube MCP"**
   - User support email: Your email
   - Developer contact: Your email
   - Click **"Save and Continue"**
   - Scopes: Click **"Add or Remove Scopes"**
     - Add: `https://www.googleapis.com/auth/youtube.readonly`
     - Add: `https://www.googleapis.com/auth/youtube.force-ssl`
   - Click **"Save and Continue"**
   - Test users: Add your email
   - Click **"Save and Continue"**

4. Back to **"Create OAuth client ID"**:
   - Application type: **Desktop app**
   - Name: **"YouTube MCP Client"**
   - Click **"Create"**

5. Download the credentials:
   - Click the download button (⬇️) next to your newly created OAuth 2.0 Client ID
   - Save the file as `youtube_credentials.json`

### 4. Place Credentials in Project

1. Move the downloaded `youtube_credentials.json` to:
   ```
   /home/logicrays/Desktop/AgentSphere-AI/src/configs/youtube_credential.json
   ```

2. Verify the file exists:
   ```bash
   ls -l src/configs/youtube_credential.json
   ```

### 5. Run Authentication Script

1. Ensure your virtual environment is activated:
   ```bash
   source .venv/bin/activate
   ```

2. Run the authentication script:
   ```bash
   python authentication/authenticate_youtube.py
   ```

3. Follow the prompts:
   - A browser window will open
   - Sign in with your Google account
   - Grant the requested permissions
   - You'll see a success message

4. Verify token file was created:
   ```bash
   ls -l src/configs/youtube_token.pickle
   ```



### 6. Test the Integration

1. Start AgentSphere-AI:
   ```bash
   python main.py
   ```

2. Test with a YouTube query:
   - "Search for Python tutorial videos"
   - "Get information about video ID: dQw4w9WgXcQ"
   - "Summarize this YouTube video: [URL]"

## Troubleshooting

### Error: "credentials.json not found"
- Make sure you've placed the credentials file in the correct location
- Check the filename is exactly `youtube_credentials.json`

### Error: "Access blocked: This app's request is invalid"
- Make sure you've added your email as a test user in the OAuth consent screen
- Verify the scopes are correctly configured

### Error: "The user has not granted the app"
- Complete the OAuth flow in the browser
- Grant all requested permissions

### Token Expired
- Delete `authentication/youtube/youtube_token.pickle`
- Run `python authentication/authenticate_youtube.py` again

## API Quotas

YouTube Data API v3 has daily quotas:
- Default quota: 10,000 units per day
- Each API call costs different units (1-100 units typically)
- Monitor usage in Google Cloud Console > APIs & Services > Dashboard

## Security Notes

- **Never commit** `youtube_credentials.json` to version control
- **Never commit** `youtube_token.pickle` to version control
- Both files are already in `.gitignore`
- Keep your credentials secure and private

## Additional Resources

- [YouTube Data API Documentation](https://developers.google.com/youtube/v3)
- [Google Cloud Console](https://console.cloud.google.com)
- [OAuth 2.0 Guide](https://developers.google.com/identity/protocols/oauth2)
