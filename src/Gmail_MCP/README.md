# Gmail MCP Integration Guide

## 📋 Overview

This directory contains a working demo client for the [Gmail MCP Server](https://github.com/theposch/gmail-mcp). The Model Context Protocol (MCP) allows AI assistants to interact with Gmail through a standardized interface.

## 🎯 What's Included

- **`gmail_mcp_client.py`** - Full-featured MCP client with tool listing and connection testing
- **`test_connection.py`** - Simple connection test script
- **`requirements.txt`** - All required Python dependencies
- **`README.md`** - This guide

## ⚙️ Prerequisites

### 1. Python Version
- **Python 3.12+** is required (the MCP server uses Python 3.12+ features)

Check your version:
```bash
python --version
```

### 2. Gmail MCP Server
Clone the server repository:
```bash
git clone https://github.com/theposch/gmail-mcp.git
cd gmail-mcp
```

### 3. Google Cloud Setup

You need Google OAuth credentials to access Gmail API:

1. **Create a Google Cloud Project**
   - Go to [Google Cloud Console](https://console.cloud.google.com/projectcreate)
   - Create a new project

2. **Enable Gmail API**
   - Visit [Gmail API Library](https://console.cloud.google.com/apis/library/gmail.googleapis.com)
   - Click "Enable"

3. **Configure OAuth Consent Screen**
   - Go to [OAuth Consent Screen](https://console.cloud.google.com/apis/credentials/consent)
   - Select "External" user type
   - Add your email as a test user
   - Add scope: `https://www.googleapis.com/auth/gmail.modify`

4. **Create OAuth Credentials**
   - Go to [Credentials](https://console.cloud.google.com/apis/credentials)
   - Click "Create Credentials" → "OAuth 2.0 Client ID"
   - Choose "Desktop app" as application type
   - Download the JSON file
   - Save it as `credentials.json`

## 🚀 Installation

### Step 1: Install Dependencies

```bash
cd src/Gmail_MCP
pip install -r requirements.txt
```

### Step 2: Configure Paths

Edit the configuration in both `gmail_mcp_client.py` and `test_connection.py`:

```python
# Update these paths
SERVER_SCRIPT = "/absolute/path/to/gmail-mcp/src/gmail/server.py"
CREDENTIALS_FILE = "/absolute/path/to/credentials.json"
TOKEN_FILE = "/absolute/path/to/token.json"  # Will be created on first run
```

## 🧪 Testing

### Quick Connection Test

```bash
python test_connection.py
```

This will:
- ✅ Connect to the Gmail MCP server
- ✅ Test the connection
- ✅ Verify server is responding

### Full Demo

```bash
python gmail_mcp_client.py
```

This will:
- ✅ Connect to the server
- ✅ List all available tools
- ✅ List all available prompts
- ✅ Show detailed information about each tool

## 🔧 Available Tools

The Gmail MCP server provides these tools:

### 📧 Email Management
- `send_email` - Send emails
- `read_email` - Read email content
- `search_emails` - Search with Gmail query syntax
- `trash_email` - Move to trash
- `mark_as_read` / `mark_as_unread` - Update read status
- `open_email_in_browser` - Open in web browser

### 📝 Drafts
- `create_draft` - Create draft emails
- `list_drafts` - List all drafts
- `edit_draft` - Modify existing drafts

### 🏷️ Labels
- `list_labels` - Get all labels
- `create_label` - Create new label
- `apply_label` / `remove_label` - Manage email labels
- `rename_label` - Rename existing label
- `delete_label` - Delete label

### 📁 Folders
- `create_folder` - Create folder (Gmail label)
- `move_to_folder` - Move emails between folders
- `list_folders` - List all folders

### 🗄️ Archive
- `archive_email` - Archive single email
- `batch_archive` - Archive multiple emails
- `list_archived_emails` - List archived emails
- `restore_from_archive` - Restore to inbox

### 🔍 Filters
- `create_filter` - Create email filter
- `list_filters` - List all filters
- `delete_filter` - Delete filter

## 💡 Usage Examples

### Example 1: List All Labels

```python
await client.call_tool("list_labels", {})
```

### Example 2: Search Unread Emails

```python
await client.call_tool("search_emails", {
    "query": "is:unread",
    "max_results": 10
})
```

### Example 3: Send Email

```python
await client.call_tool("send_email", {
    "to": "recipient@example.com",
    "subject": "Hello from MCP!",
    "body": "This email was sent via Gmail MCP"
})
```

### Example 4: Create Draft

```python
await client.call_tool("create_draft", {
    "to": "recipient@example.com",
    "subject": "Draft Email",
    "body": "This is a draft"
})
```

## 🔐 Authentication Flow

On first run:
1. The server will open your browser
2. Sign in to your Google account
3. Grant permissions to the app
4. A `token.json` file will be created
5. Subsequent runs will use the saved token

## ❓ Can This Run Locally?

**YES!** ✅ This can absolutely run locally. Here's what you need:

### Requirements for Local Execution:
1. **Python 3.12+** installed on your machine
2. **Gmail MCP server** cloned locally
3. **Google OAuth credentials** (credentials.json)
4. **Internet connection** (to communicate with Gmail API)

### What Runs Locally:
- ✅ The MCP server (runs as a local Python process)
- ✅ The MCP client (your demo code)
- ✅ OAuth authentication (browser-based, one-time)

### What Requires Internet:
- 🌐 Gmail API calls (reading/sending emails)
- 🌐 Initial OAuth authentication

### Architecture:
```
Your Machine (Local)
├── Gmail MCP Server (Python process)
│   └── Communicates via stdio
├── Your Client Code (Python)
│   └── Connects to server via MCP protocol
└── Internet Connection
    └── Gmail API (Google's servers)
```

## 🐛 Troubleshooting

### Error: "Python 3.12+ required"
- Install Python 3.12 or higher
- Use `python3.12` explicitly if you have multiple versions

### Error: "Credentials file not found"
- Ensure you've downloaded OAuth credentials from Google Cloud
- Update the `CREDENTIALS_FILE` path in the code

### Error: "Server script not found"
- Clone the gmail-mcp repository
- Update the `SERVER_SCRIPT` path to point to `src/gmail/server.py`

### Error: "Module 'mcp' not found"
- Run `pip install -r requirements.txt`
- Ensure you're using the correct Python environment

### OAuth Browser Doesn't Open
- The server will print a URL to the console
- Copy and paste it into your browser manually

## 📚 Additional Resources

- [Gmail MCP Repository](https://github.com/theposch/gmail-mcp)
- [Model Context Protocol Docs](https://modelcontextprotocol.io/)
- [Gmail API Documentation](https://developers.google.com/gmail/api)

## 🎉 Next Steps

1. Run the connection test to verify setup
2. Explore available tools with the demo client
3. Integrate into your AgentSphere-AI project
4. Build custom workflows using Gmail tools

---

**Note**: The first run will require browser-based OAuth authentication. After that, the token is saved and reused automatically.
