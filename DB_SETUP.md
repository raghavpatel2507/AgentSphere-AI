# PostgreSQL Database Setup & Configuration

This guide covers the complete setup for the PostgreSQL persistence layer in AgentSphere-AI.

## 1. Dependencies

Ensure the following packages are installed (managed via `requirements.txt` or `pyproject.toml`):

- **Core Database**: `sqlalchemy`, `alembic`
- **Drivers**: `asyncpg` (for async operations), `psycopg[binary]` (for LangGraph checkpointer)
- **LangGraph**: `langgraph-checkpoint-postgres`

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
Ensure your PostgreSQL server is running and create the database:
```bash
createdb agentsphere
```

### Step B: Run Migrations
Initialize the schema (tables for tenants, configs, etc.):
```bash
alembic upgrade head
```

### Step C: Initialize Default Tenant
Create the default tenant and thread for local testing:
```bash
python scripts/init_default_tenant.py
```

### Step D: Migrate Configurations (Optional)
Move existing JSON configs (like `gmail_token.json`) to the database:
```bash
python scripts/migrate_configs_to_db.py
```

## 4. How It Works

### Architecture
- **Multi-Tenancy**: Data is isolated by `tenant_id`.
- **Persistence**: LangGraph state (chat history) is stored in `checkpoints` table.
- **Configuration**: Tenant settings (API keys, tokens) are stored in `tenant_configs` table.

### Key Files
- `src/core/config/database.py`: SQLAlchemy models and connection logic.
- `src/core/state/checkpointer.py`: LangGraph checkpointer setup.
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
3. Resume conversation from the last checkpoint (if any).
