# AgentSphere-AI Backend API Documentation

## Base URL
```
http://localhost:8000/api/v1
```

## Authentication
All protected endpoints require a Bearer token in the Authorization header:
```
Authorization: Bearer <access_token>
```

---

## 1. Authentication (`/auth`)

### POST `/auth/register`
Create a new user account.

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "securepassword123",
  "full_name": "John Doe"
}
```

**Response (201):**
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "full_name": "John Doe",
  "is_active": true,
  "hitl_config": {...},
  "preferences": {},
  "created_at": "2025-12-26T12:00:00Z",
  "last_login_at": null
}
```

---

### POST `/auth/login`
Authenticate and receive tokens.

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "securepassword123"
}
```

**Response (200):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 900
}
```

---

### POST `/auth/refresh`
Refresh expired access token.

**Request Body:**
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response (200):** Same as login response.

---

### POST `/auth/logout`
🔒 **Requires Auth**

Logout user (client should discard tokens).

**Response (200):**
```json
{
  "message": "Successfully logged out",
  "success": true
}
```

---

### GET `/auth/me`
🔒 **Requires Auth**

Get current user profile.

**Response (200):**
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "full_name": "John Doe",
  "is_active": true,
  "hitl_config": {
    "enabled": true,
    "mode": "denylist",
    "sensitive_tools": ["*google*", "*delete*"],
    "approval_message": "Execution requires your approval."
  },
  "preferences": {},
  "created_at": "2025-12-26T12:00:00Z",
  "last_login_at": "2025-12-26T12:00:00Z"
}
```

---

### PATCH `/auth/me`
🔒 **Requires Auth**

Update profile.

**Request Body:**
```json
{
  "full_name": "Jane Doe",
  "preferences": {"theme": "dark"}
}
```

---

### GET `/auth/me/hitl-config`
🔒 **Requires Auth**

Get HITL configuration.

---

### PATCH `/auth/me/hitl-config`
🔒 **Requires Auth**

Update HITL configuration.

**Request Body:**
```json
{
  "enabled": true,
  "mode": "denylist",
  "sensitive_tools": ["*delete*", "*write*"],
  "approval_message": "Please approve this action"
}
```

---

## 2. Chat (`/chat`)

### POST `/chat/new`
🔒 **Requires Auth**

Create a new conversation.

**Request Body:**
```json
{
  "title": "My Conversation",
  "initial_message": "Hello, how are you?"
}
```

**Response (201):**
```json
{
  "thread_id": "thread_abc123def456",
  "conversation_id": "uuid",
  "title": "My Conversation",
  "created_at": "2025-12-26T12:00:00Z"
}
```

---

### POST `/chat/{thread_id}/message`
🔒 **Requires Auth**

Send a message and receive streaming response (SSE).

**Request Body:**
```json
{
  "content": "What is the weather today?"
}
```

**Response:** Server-Sent Events stream
```
data: {"type": "status", "content": "Processing your request..."}

data: {"type": "token", "content": "The"}

data: {"type": "token", "content": " weather"}

data: {"type": "tool_start", "tool": "weather_api", "inputs": {"city": "NYC"}}

data: {"type": "tool_end", "tool": "weather_api", "output": "72°F, Sunny"}

data: {"type": "approval_required", "request_id": "uuid", "tool_name": "send_email", "tool_args": {...}}

data: {"type": "done"}
```

**Event Types:**
| Type | Description |
|------|-------------|
| `status` | Processing status update |
| `token` | LLM response token (stream text) |
| `tool_start` | Tool execution started |
| `tool_end` | Tool execution completed |
| `approval_required` | HITL approval needed |
| `error` | Error occurred |
| `done` | Stream complete |

---

### GET `/chat/{thread_id}/status`
🔒 **Requires Auth**

Check chat processing status.

**Response (200):**
```json
{
  "thread_id": "thread_abc123def456",
  "is_processing": false,
  "pending_approval": null,
  "last_activity": "2025-12-26T12:00:00Z"
}
```

---

### GET `/chat/{thread_id}/messages`
🔒 **Requires Auth**

Get messages for a conversation.

**Query Parameters:**
- `limit` (int, default: 100)

**Response (200):**
```json
[
  {
    "id": "uuid",
    "conversation_id": "uuid",
    "role": "USER",
    "content": "Hello",
    "metadata": {},
    "created_at": "2025-12-26T12:00:00Z"
  }
]
```

---

## 3. Conversations (`/conversations`)

### GET `/conversations/`
🔒 **Requires Auth**

List user's conversations.

**Query Parameters:**
- `page` (int, default: 1)
- `page_size` (int, default: 20, max: 100)
- `status` (string, optional: ACTIVE, ARCHIVED)
- `include_deleted` (bool, default: false)
- `search` (string, optional)

**Response (200):**
```json
{
  "items": [
    {
      "id": "uuid",
      "thread_id": "thread_abc123",
      "title": "My Chat",
      "status": "ACTIVE",
      "message_count": 10,
      "last_message_preview": "Sure, I can help with...",
      "created_at": "2025-12-26T12:00:00Z",
      "updated_at": "2025-12-26T12:00:00Z",
      "is_deleted": false
    }
  ],
  "total": 50,
  "page": 1,
  "page_size": 20,
  "has_more": true
}
```

---

### GET `/conversations/{conversation_id}`
🔒 **Requires Auth**

Get conversation with messages.

**Query Parameters:**
- `include_messages` (bool, default: true)
- `message_limit` (int, default: 100)

---

### PATCH `/conversations/{conversation_id}/title`
🔒 **Requires Auth**

Update conversation title.

**Request Body:**
```json
{
  "title": "New Title"
}
```

---

### DELETE `/conversations/{conversation_id}`
🔒 **Requires Auth**

Soft delete (or hard delete if specified).

**Query Parameters:**
- `hard_delete` (bool, default: false)

---

### PATCH `/conversations/{conversation_id}/restore`
🔒 **Requires Auth**

Restore a soft-deleted conversation.

---

### PATCH `/conversations/{conversation_id}/archive`
🔒 **Requires Auth**

Archive a conversation.

---

## 4. MCP Servers (`/mcp/servers`)

### GET `/mcp/servers/`
🔒 **Requires Auth**

List user's MCP servers.

**Response (200):**
```json
{
  "servers": [
    {
      "id": "uuid",
      "name": "github",
      "enabled": true,
      "config": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-github"],
        "env": {"GITHUB_TOKEN": "***masked***"}
      },
      "disabled_tools": [],
      "created_at": "2025-12-26T12:00:00Z",
      "updated_at": "2025-12-26T12:00:00Z"
    }
  ],
  "total": 1
}
```

---

### POST `/mcp/servers/`
🔒 **Requires Auth**

Add a new MCP server.

**Request Body:**
```json
{
  "name": "github",
  "config": {
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-github"],
    "env": {"GITHUB_TOKEN": "ghp_xxxxx"}
  },
  "enabled": true
}
```

---

### GET `/mcp/servers/{server_name}`
🔒 **Requires Auth**

Get server details.

---

### PATCH `/mcp/servers/{server_name}`
🔒 **Requires Auth**

Update server configuration.

**Request Body:**
```json
{
  "config": {...},
  "enabled": true
}
```

---

### DELETE `/mcp/servers/{server_name}`
🔒 **Requires Auth**

Remove a server.

---

### POST `/mcp/servers/{server_name}/enable`
🔒 **Requires Auth**

Enable a server.

---

### POST `/mcp/servers/{server_name}/disable`
🔒 **Requires Auth**

Disable a server.

---

### POST `/mcp/servers/{server_name}/test`
🔒 **Requires Auth**

Test server connection.

**Response (200):**
```json
{
  "success": true,
  "message": "Successfully connected to 'github'",
  "tools_count": 15,
  "error": null
}
```

---

## 5. MCP Tools (`/mcp/tools`)

### GET `/mcp/tools/`
🔒 **Requires Auth**

List all available tools.

**Response (200):**
```json
{
  "tools": [
    {
      "name": "create_issue",
      "description": "Create a GitHub issue",
      "server_name": "github",
      "enabled": true,
      "requires_approval": false,
      "input_schema": {...}
    }
  ],
  "total": 50
}
```

---

### GET `/mcp/tools/{server_name}`
🔒 **Requires Auth**

List tools for a specific server.

---

### POST `/mcp/tools/{server_name}/{tool_name}/enable`
🔒 **Requires Auth**

Enable a tool.

---

### POST `/mcp/tools/{server_name}/{tool_name}/disable`
🔒 **Requires Auth**

Disable a tool.

---

## 6. MCP Registry (`/mcp/registry`)

### GET `/mcp/registry/apps`
List available MCP app templates.

**Query Parameters:**
- `category` (string, optional)
- `search` (string, optional)

**Response (200):**
```json
{
  "apps": [
    {
      "id": "github",
      "name": "GitHub",
      "description": "GitHub API access",
      "icon": "🐙",
      "category": "Development",
      "config_template": {...},
      "auth_fields": [
        {"name": "GITHUB_TOKEN", "label": "Personal Access Token", "type": "password", "required": true}
      ],
      "is_custom": false
    }
  ],
  "total": 10,
  "categories": ["Development", "Productivity", "Communication"]
}
```

---

### GET `/mcp/registry/apps/{app_id}`
Get details for a specific registry app.

---

### GET `/mcp/registry/categories`
List all app categories.

---

## 7. HITL - Human-in-the-Loop (`/hitl`)

### GET `/hitl/pending`
🔒 **Requires Auth**

List pending approval requests.

**Query Parameters:**
- `limit` (int, default: 50)
- `include_expired` (bool, default: false)

**Response (200):**
```json
{
  "requests": [
    {
      "id": "uuid",
      "user_id": "uuid",
      "conversation_id": "uuid",
      "thread_id": "thread_abc123",
      "tool_name": "send_email",
      "tool_args": {"to": "john@example.com", "subject": "Hello"},
      "server_name": "gmail",
      "status": "PENDING",
      "decision_at": null,
      "decision_reason": null,
      "created_at": "2025-12-26T12:00:00Z",
      "expires_at": "2025-12-26T12:05:00Z",
      "is_expired": false
    }
  ],
  "total": 1,
  "pending_count": 1
}
```

---

### GET `/hitl/{request_id}`
🔒 **Requires Auth**

Get HITL request details.

---

### POST `/hitl/{request_id}/approve`
🔒 **Requires Auth**

Approve a pending request.

**Request Body (optional):**
```json
{
  "reason": "Looks safe to proceed"
}
```

---

### POST `/hitl/{request_id}/reject`
🔒 **Requires Auth**

Reject a pending request.

**Request Body (optional):**
```json
{
  "reason": "Don't send this email"
}
```

---

### POST `/hitl/{request_id}/approve-and-whitelist`
🔒 **Requires Auth**

Approve and whitelist the tool.

**Request Body:**
```json
{
  "reason": "Trust this tool",
  "whitelist_duration": "session"
}
```

---

## 8. OAuth (`/oauth`)

### GET `/oauth/{service}/auth-url`
🔒 **Requires Auth**

Get OAuth authorization URL.

**Query Parameters:**
- `redirect_uri` (string, required) - Frontend callback URL

**Supported Services:** `gmail`, `youtube`, `google-drive`, `zoho`

**Response (200):**
```json
{
  "auth_url": "https://accounts.google.com/o/oauth2/v2/auth?...",
  "service": "gmail"
}
```

---

### POST `/oauth/{service}/callback`
🔒 **Requires Auth**

Exchange OAuth code for tokens.

**Request Body:**
```json
{
  "code": "4/0AY0e-g...",
  "redirect_uri": "http://localhost:3000/oauth/callback"
}
```

---

### GET `/oauth/{service}/status`
🔒 **Requires Auth**

Check OAuth status.

**Response (200):**
```json
{
  "service": "gmail",
  "authenticated": true,
  "scopes": ["https://www.googleapis.com/auth/gmail.modify"],
  "expires_at": "2025-12-26T13:00:00Z"
}
```

---

### DELETE `/oauth/{service}/revoke`
🔒 **Requires Auth**

Revoke OAuth tokens.

---

### GET `/oauth/services`
List supported OAuth services.

---

## 9. WebSocket (`/ws`)

### WS `/ws/{thread_id}?token={jwt}`

Real-time bidirectional chat streaming.

**Connection URL:**
```
ws://localhost:8000/api/v1/ws/thread_abc123?token=eyJhbG...
```

**Send Message:**
```json
{"type": "message", "content": "Hello!"}
```

**Send HITL Decision:**
```json
{"type": "hitl_decision", "request_id": "uuid", "approved": true}
```

**Ping:**
```json
{"type": "ping"}
```

**Receive Events:** Same as SSE events (status, token, tool_start, tool_end, etc.)

---

## Error Responses

All errors follow this format:

```json
{
  "detail": "Error description"
}
```

**Common Status Codes:**
| Code | Description |
|------|-------------|
| 400 | Bad Request - Invalid input |
| 401 | Unauthorized - Missing/invalid token |
| 403 | Forbidden - Access denied |
| 404 | Not Found |
| 409 | Conflict - Resource already exists |
| 422 | Validation Error |
| 500 | Internal Server Error |

---

## Rate Limits

Currently no rate limiting implemented. Consider implementing for production.
