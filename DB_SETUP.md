# PostgreSQL Database Setup & Configuration

This guide covers the complete setup for the PostgreSQL persistence layer in AgentSphere-AI.

## 1. Dependencies

Ensure the following packages are installed (managed via `requirements.txt` or `pyproject.toml`):

- **Core Database**: `sqlalchemy`, `alembic`
- **Drivers**: `asyncpg` (for async operations)

## 2. Environment Configuration

Create or update your `.env` file with these variables:

```ini
# Database Connection
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/agentsphere
# Note: The system automatically handles conversion to psycopg format where needed.

# Connection Pooling (Optional)
POSTGRES_POOL_SIZE=20
POSTGRES_MAX_OVERFLOW=10

# Default Tenant (for CLI/Testing)
DEFAULT_TENANT_ID=default
DEFAULT_TENANT_API_KEY=dev_api_key_12345
```

## 3. Database Initialization

### Step A: Create Database
Ensure your PostgreSQL server is running and create the database named `agentsphere`.

### Step B: Run Initial Setup
The system will automatically attempt to initialize tables on startup. However, the recommended way to ensure the schema and default seed data are ready is to run:
```bash
alembic upgrade head
```
This command will create all tables (`tenants`, `tenant_configs`, `conversations`, `messages`) and insert a default dev tenant.

## 4. How It Works

### Architecture
- **Multi-Tenancy**: Data is isolated by `tenant_id`.
- **Persistence**: Conversation history is stored in `conversations` and `messages` tables.
- **Configuration**: Tenant settings (API keys, tokens) are stored in `tenant_configs` table.

### Key Files
- `src/core/config/database.py`: SQLAlchemy models and connection logic.
- `src/core/state/conversation_store.py`: Direct database operations for messages.
- `src/core/state/thread_manager.py`: Thread and session management.
- `src/core/config/tenant_config.py`: Manager for loading configs from DB.

## 5. Usage in Code

The system automatically handles connection and persistence.

**Starting the Chat:**
```bash
python main.py
```
This will:
1. Connect to PostgreSQL.
2. Load the default tenant.
3. Resume conversation from the last session (if any).
