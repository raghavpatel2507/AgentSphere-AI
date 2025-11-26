# Migration Guide: Universal MCP Manager

We have migrated AgentSphere-AI to a new **Universal MCP Manager** system. This allows you to add any type of MCP server (Node.js, Python, Docker, Remote) just by editing a JSON configuration file, without writing any code.

## Key Changes

1.  **Single Configuration File**: All MCP servers are now configured in `mcp_config.json`.
2.  **No More Client Code**: You don't need to write Python client classes for new MCP servers.
3.  **Dynamic Experts**: Agents are automatically created based on the tools available in your MCP servers.
4.  **Multi-LLM Support**: Switch between OpenAI, Gemini, Claude, and Groq easily.

## How to Add a New MCP Server

Simply add an entry to `mcp_config.json`:

### Node.js Server
```json
{
  "name": "filesystem",
  "type": "node",
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/allowed/dir"],
  "enabled": true,
  "expert_role": "File system manager"
}
```

### Python Server
```json
{
  "name": "my-python-server",
  "type": "python",
  "command": "python",
  "args": ["path/to/server.py"],
  "enabled": true,
  "expert_role": "Python server specialist"
}
```

### Docker Server
```json
{
  "name": "my-db-server",
  "type": "docker",
  "args": ["my-docker-image:latest"],
  "enabled": true,
  "expert_role": "Database specialist"
}
```

## Configuring LLMs

You can now configure your LLM provider in `mcp_config.json` or via environment variables.

### Option 1: `mcp_config.json`
```json
"llm": {
  "provider": "gemini",
  "model": "gemini-2.0-flash-exp",
  "temperature": 0.7,
  "max_tokens": 100000
}
```

### Option 2: Environment Variables (`.env`)
```env
LLM_PROVIDER=openai
MODEL_NAME=gpt-4o
MAX_TOKENS=100000
```

Supported providers: `openai`, `gemini`, `claude`, `groq`.

## Troubleshooting

-   **Server not connecting?** Check the logs in the console. The manager will try to reconnect automatically.
-   **Tools not showing up?** Ensure `enabled: true` is set in the config.
-   **LLM errors?** Verify your API keys in `.env`.

## Architecture

-   `src/core/mcp/manager.py`: Main manager class.
-   `src/core/mcp/handlers/`: Handlers for different server types.
-   `src/core/agents/expert_factory.py`: Generates agents from tools.
-   `src/core/llm/provider.py`: LLM abstraction layer.
