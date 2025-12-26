# Backend Migration & Setup Guide

## Prerequisites

- Python 3.11+
- PostgreSQL 14+
- Node.js 18+ (for MCP servers)

---

## Step 1: Install Dependencies

```bash
# Navigate to project root
cd AgentSphere-AI

# Create and activate virtual environment
python -m venv .venv

# Windows
.\.venv\Scripts\activate

# Linux/Mac
source .venv/bin/activate

# Install dependencies using uv (recommended)
uv sync

# OR using pip
pip install -e .
```

---

## Step 2: Configure Environment Variables

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

**Required new variables for the backend:**

```env
# ============================================
# JWT Configuration (REQUIRED)
# ============================================
# Secret key for JWT tokens (generate a secure random string)
# IMPORTANT: Change this in production!
JWT_SECRET_KEY=your-super-secret-jwt-key-change-in-production

# JWT Algorithm (default: HS256)
JWT_ALGORITHM=HS256

# Access token expiry (default: 15 minutes)
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15

# Refresh token expiry (default: 7 days)
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# ============================================
# App Configuration
# ============================================
APP_NAME=AgentSphere-AI
APP_VERSION=2.0.0
DEBUG=true

# ============================================
# CORS (comma-separated origins)
# ============================================
CORS_ORIGINS=http://localhost:3000,http://localhost:5173

# ============================================
# HITL Configuration
# ============================================
# Timeout for HITL requests (default: 5 minutes)
HITL_REQUEST_TIMEOUT_SECONDS=300

# ============================================
# OAuth (Optional - for Gmail, YouTube, etc.)
# ============================================
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
ZOHO_CLIENT_ID=your-zoho-client-id
ZOHO_CLIENT_SECRET=your-zoho-client-secret
```

---

## Step 3: Run Database Migrations

The backend requires new database tables. Run Alembic migrations:

```bash
# Make sure you're in the project root with .venv activated
cd AgentSphere-AI

# Check current migration status
alembic current

# Apply all pending migrations
alembic upgrade head
```

### New Tables Created:

| Table | Purpose |
|-------|---------|
| `hitl_requests` | HITL (Human-in-the-Loop) pending approvals |
| `oauth_tokens` | Per-user encrypted OAuth credentials |

### Schema Changes:

| Table | Changes |
|-------|---------|
| `conversations` | Added `is_deleted`, `deleted_at` (soft delete) |
| `users` | Added `tenant_id`, `last_login_at`, `preferences` |
| `mcp_server_configs` | Added `disabled_tools` array |

---

## Step 4: Start the Backend Server

```bash
# Navigate to backend folder
cd backend

# Run with uvicorn (development)
python -m uvicorn app.main:app --reload --port 8000

# OR run from project root
cd AgentSphere-AI
python -m uvicorn backend.app.main:app --reload --port 8000
```

**Server will be available at:**
- API: http://localhost:8000
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Health Check: http://localhost:8000/health

---

## Step 5: Verify Installation

### 5.1 Check Health Endpoint
```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "version": "2.0.0",
  "service": "AgentSphere-AI"
}
```

### 5.2 Test Registration
```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "password123", "full_name": "Test User"}'
```

### 5.3 Test Login
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "password123"}'
```

---

## Troubleshooting

### Issue: `ModuleNotFoundError: No module named 'backend'`
**Solution:** Run uvicorn from the `backend` folder:
```bash
cd backend
python -m uvicorn app.main:app --reload --port 8000
```

### Issue: `argon2: no backends available`
**Solution:** Install argon2-cffi:
```bash
# If using system Python
pip install argon2-cffi

# If using uv (already in pyproject.toml)
uv sync
```

### Issue: Database connection errors
**Solution:** Verify PostgreSQL is running and credentials in `.env` are correct:
```bash
# Test connection
psql -U postgres -d agentsphere -c "SELECT 1"
```

### Issue: Migration fails with "type already exists"
**Solution:** Drop orphaned types and retry:
```bash
# Connect to database and drop orphaned enum
python -c "import psycopg2; conn = psycopg2.connect('postgresql://postgres:root@localhost:5432/agentsphere'); cur = conn.cursor(); cur.execute('DROP TYPE IF EXISTS hitl_status CASCADE'); conn.commit(); conn.close()"

# Retry migration
alembic upgrade head
```

---

## Running in Production

```bash
# Use gunicorn with uvicorn workers
pip install gunicorn

gunicorn backend.app.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000
```

**Production Checklist:**
- [ ] Set `DEBUG=false` in `.env`
- [ ] Generate secure `JWT_SECRET_KEY`
- [ ] Configure proper `CORS_ORIGINS`
- [ ] Set up SSL/TLS (HTTPS)
- [ ] Configure database connection pooling
- [ ] Set up logging and monitoring
