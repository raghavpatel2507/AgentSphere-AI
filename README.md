# AgentSphere-AI (v2.0) - Ground-Up Architecture

AgentSphere-AI is a high-performance agentic system designed for multi-tool orchestration using the Model Context Protocol (MCP). The v2.0 architecture is focused on speed, reliability, and proactive execution.

## 🚀 Key Features

- **Planner-Agent Architecture**: A streamlined two-stage flow:
  1. **Planner**: Analyzes intent and routes to specific MCP servers.
  2. **Agent**: Proactively executes tools with self-healing and loop protection.
- **Universal MCP Management**: Powered by `mcp-use`, supporting dynamic server connection, tool discovery, and high-level orchestration.
- **PostgreSQL Persistence**: Full state management using LangGraph checkpointers with automatic signature filtering to save tokens and DB space.
- **Real-time Streaming**: Token-by-token streaming for all responses, including tool-heavy tasks.
- **Instant Connection**: Only connects to the necessary MCP servers for the current task, ensuring rapid startup.

## 🏗️ Technical Architecture

### 1. The Planner (`src/core/agents/planner.py`)
The **Planner** serves as the system's "ROUTER". It uses high-level server descriptions to decide which tools are needed.
- **Common Knowledge Rule**: Responds directly to general questions without using tools.
- **Selective Routing**: Only activates the MCP servers required for the specific user request.

### 2. The Agent (`src/core/agents/agent.py`)
The **Agent** is a "PROACTIVE EXECUTOR". It is initialized fresh every turn with the specific tools provided by the Planner.
- **Execution Over Conversation**: Strictly prioritizes tool usage for tasks.
- **Self-Healing**: Automatically analyzes tool errors and tries alternative approaches.
- **Loop Protection**: Detects and stops recurring failed calls to prevent token drain.

### 3. MCP Manager (`src/core/mcp/manager.py`)
Orchestrates connections to external services defined in `multi_server_config.json`.
- **Deferred Connection**: Servers are only started when the Planner requires them.
- **HITL Integration**: Support for Human-In-The-Loop approval for sensitive tools.

### 4. Persistence (`src/core/state/thread_manager.py`)
Handles saving and loading conversation history to a PostgreSQL backend.
- **Thread Isolation**: Conversations are isolated by `thread_id` and `tenant_id`.
- **Checkpointing**: Reliable state recovery via LangGraph `AsyncPostgresSaver`.

## 🛠️ Configuration

### `multi_server_config.json`
Define your MCP servers here. This file is the source of truth for the system's capabilities.
```json
{
  "mcpServers": {
    "google-drive": {
      "command": "npx",
      "args": ["@modelcontextprotocol/server-google-drive"],
      "env": { "GOOGLE_APPLICATION_CREDENTIALS": "..." }
    }
  }
}
```



## 🏁 Getting Started

1. **Setup Database**: Ensure PostgreSQL is running and follow [DB_SETUP.md](DB_SETUP.md).
2. **Install Dependencies**: `pip install -r requirements.txt`
3. **Run Terminal Chat**: `python main.py`
4. **Run Streamlit UI**: `streamlit run streamlit_app.py`

---
*Built with ❤️ by AgentSphere-AI Team*
