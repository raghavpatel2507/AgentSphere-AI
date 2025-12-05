# AgentSphere-AI Project Overview

## 1. High-Level Architecture

**AgentSphere-AI** is an advanced agentic system designed to orchestrate multiple specialized AI agents ("Experts") to solve complex tasks. It uses a **Supervisor-Worker** architecture where a central "Supervisor" agent breaks down user requests and delegates them to the appropriate specialized agents.

The core technology stack includes:
-   **LangGraph**: For managing the state and workflow of agents.
-   **LangChain**: For agent creation and tool handling.
-   **Model Context Protocol (MCP)**: A standard for connecting AI models to external tools and data sources (like Google Drive, GitHub, Figma, etc.).

### How It Works (The Flow)

1.  **User Request**: You send a request (e.g., "Find the latest AI news and save it to a Google Doc").
2.  **Supervisor Agent**: The Supervisor receives the request. It looks at its team of available "Experts".
3.  **Routing**:
    *   It sees "Find news" -> Delegates to `websearch_expert`.
    *   It sees "Save to Google Doc" -> Delegates to `google_drive_expert`.
4.  **Execution**:
    *   `websearch_expert` uses search tools to get information.
    *   `google_drive_expert` uses Google Drive MCP tools to create the document.
5.  **Final Response**: The Supervisor collects the results and presents a final answer to you.

---

## 2. Key Components & File Explanation

### A. Configuration (`mcp_config.json`)
**Purpose**: The blueprint of your system. It defines which "Experts" are available.
-   **`mcp_servers`**: A list of external tool providers. Each entry (like `github`, `google-drive`, `filesystem`) defines:
    -   `command`: How to start the server (e.g., `npx`, `python`).
    -   `env`: API keys and environment variables.
    -   `expert_role`: A description of what this expert does (used by the Supervisor to know when to call it).

### B. The Supervisor (`src/core/agents/supervisor.py`)
**Purpose**: The "Brain" or "Manager" of the operation.
-   **`get_active_agents()`**: This function builds the team. It combines:
    -   **Static Agents**: Always there (WebSearch, Math, Python).
    -   **Dynamic Experts**: Created based on `mcp_config.json`.
-   **`get_dynamic_supervisor_prompt()`**: This is where the magic happens. It dynamically writes the Supervisor's instructions. It reads the config and adds lines like:
    > "If the user asks about GitHub, route to github_expert."
    This ensures the Supervisor knows about new tools automatically when you add them to the config.
-   **`create_workflow()`**: Sets up the LangGraph workflow, connecting the Supervisor to all the agents.

### C. The Expert Factory (`src/core/agents/expert_factory.py`)
**Purpose**: The "Recruiter" that hires and trains the experts.
-   **`create_all_experts()`**:
    1.  Reads `mcp_config.json`.
    2.  For each enabled server (e.g., "figma"), it connects to it.
    3.  It fetches the available tools (e.g., `get_file`, `get_comments`).
    4.  It creates a new AI Agent (`figma_expert`) and gives it those tools.
    5.  It gives the agent a specific "System Prompt" telling it how to be a Figma specialist.

### D. The MCP Manager (`src/core/mcp/manager.py`)
**Purpose**: The "Connector" or "IT Department".
-   **`MCPManager` Class**: A singleton (only one instance exists) that manages connections.
-   **`initialize()`**: Starts up all the servers defined in `mcp_config.json` (Node.js servers, Python scripts, etc.).
-   **`call_tool()`**: When an agent wants to use a tool, this manager routes the request to the correct running server and returns the result.
-   **`_process_tool_result()`**: Handles things like saving large images to files instead of clogging up the chat history.

### E. The Tool Registry (`src/core/mcp/tool_registry.py`)
**Purpose**: The "Phonebook" or "Catalog" for all tools.
-   **`ToolRegistry` Class**: Centralizes all available tools from all connected servers.
-   **`register_tool()`**: Handles name conflicts (e.g., if two servers have a "search" tool, it renames one to `server_search`).
-   **`get_tool_schemas()`**: Converts internal tool definitions into the specific JSON format that the AI (LLM) understands, so it knows how to use them.

---

## 3. How to Work With This Project

### Adding a New Tool/Service
1.  **Edit `mcp_config.json`**: Add a new entry to `mcp_servers`.
    ```json
    {
      "name": "my-new-tool",
      "type": "node",
      "command": "npx",
      "args": ["my-mcp-server-package"],
      "enabled": true,
      "expert_role": "Specialist for my new tool"
    }
    ```
2.  **Restart**: When the application starts, `MCPManager` will see the new config, start the server, and `ExpertFactory` will automatically create a `my-new-tool_expert`.
3.  **Use It**: The Supervisor will automatically know to route tasks to this new expert because `supervisor.py` dynamically updates its prompt.

### Debugging
-   **Agent Issues**: Check `src/core/agents/expert_factory.py` to see how prompts are generated.
-   **Connection Issues**: Check `src/core/mcp/manager.py` and the logs to see if servers are starting correctly.
-   **Routing Issues**: Check `src/core/agents/supervisor.py` to see if the Supervisor's prompt is correctly describing the new expert.
