# Execution Workflow: How a New MCP Tool Works

This guide explains exactly what happens when you add a new MCP server (like "Spotify" or "Jira") to the system. We will trace the flow file-by-file.

## Scenario
You just added a new tool to `mcp_config.json`.
```json
{
  "name": "spotify",
  "type": "node",
  "expert_role": "Spotify specialist"
}
```

---

## Phase 1: Startup & Initialization
**Goal**: The system wakes up, sees the new config, and connects to the tool.

### 1. `src/core/mcp/manager.py` (The Bootstrapper)
*   **Action**: When the app starts, `MCPManager.initialize()` runs.
*   **What happens**:
    1.  It reads `mcp_config.json`.
    2.  It sees `"spotify"`.
    3.  It calls `_create_handler()` which actually runs the command (e.g., `npx spotify-mcp`).
    4.  It calls `_init_server()` to connect to the running process.
    5.  It asks the Spotify server: *"What tools do you have?"* (e.g., `play_song`, `search_artist`).

### 2. `src/core/mcp/tool_registry.py` (The Registration)
*   **Action**: `MCPManager` calls `registry.register_tool()` for every tool it found.
*   **What happens**:
    1.  The registry saves `play_song` and tags it as belonging to the "spotify" server.
    2.  If there was already a `play_song` tool from another server, it renames this one to `spotify_play_song` to avoid crashes.

---

## Phase 2: Agent Creation
**Goal**: The system creates a specialized AI agent that knows how to use these new tools.

### 3. `src/core/agents/expert_factory.py` (The Builder)
*   **Action**: `create_all_experts()` runs.
*   **What happens**:
    1.  It loops through the config and sees "spotify".
    2.  It asks the Registry: *"Give me all tools for 'spotify'."*
    3.  It creates a new LangChain Agent named `spotify_expert`.
    4.  It gives this agent the `play_song` tool.
    5.  It gives the agent a System Prompt: *"You are a Spotify specialist..."*

### 4. `src/core/agents/supervisor.py` (The Manager Update)
*   **Action**: `get_dynamic_supervisor_prompt()` runs.
*   **What happens**:
    1.  It reads the config again.
    2.  It dynamically adds a line to the Supervisor's instructions:
        > "   - spotify_expert: Spotify specialist"
        > "   - spotify related tasks → spotify_expert"
    3.  **Result**: The Supervisor now knows that if you ask for music, it should talk to the `spotify_expert`.

---

## Phase 3: Execution Flow
**Goal**: You ask a question, and the code executes the tool.

**User Request**: "Play some jazz music."

### 5. `src/core/agents/supervisor.py` (Routing)
*   **Action**: The Supervisor LLM reads your request.
*   **Logic**: It sees "Play music" and checks its list. It matches "music" to `spotify_expert`.
*   **Output**: It decides to route the task to `spotify_expert`.

### 6. `src/core/agents/expert_factory.py` (The Expert Agent)
*   **Action**: The `spotify_expert` receives the task "Play some jazz music".
*   **Logic**: It looks at its tools. It sees `play_song`.
*   **Output**: It decides to call `play_song(genre="jazz")`.

### 7. `src/core/mcp/manager.py` (The Execution)
*   **Action**: The agent calls the tool, which triggers `MCPManager.call_tool("play_song", ...)`.
*   **Logic**:
    1.  It looks up "play_song" in the Registry.
    2.  It sees it belongs to the "spotify" server.
    3.  It sends a JSON message to the running `npx spotify-mcp` process.
*   **Result**: The Spotify server plays the music and returns "Playing Jazz".

### 8. Final Response
*   The `spotify_expert` reports back: "I have started playing jazz."
*   The Supervisor tells you: "I've started playing some jazz music for you."
