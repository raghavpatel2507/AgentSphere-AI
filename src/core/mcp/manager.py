import os
import asyncio
import logging
import json
from typing import Dict, List, Any, Optional, Type
from pydantic import create_model, Field, BaseModel

# Import mcp-use components
from mcp_use.client import MCPClient
from langchain_core.tools import Tool, StructuredTool
from langgraph.types import interrupt
import fnmatch


logger = logging.getLogger(__name__)

class MCPManager:
    """
    Universal MCP Manager using mcp-use library.
    Orchestrates all MCP servers, handles configuration, and manages tools.
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MCPManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self.config_path = "mcp_config.json"
        
        # Central MCPClient to manage all servers
        self._mcp_client: Optional[MCPClient] = None
        
        # Map server_name -> MCPSession
        self.server_sessions: Dict[str, Any] = {}
        
        self.config_data = {}
        # Runtime cache for session-approved tools
        self.whitelisted_tools: set[str] = set()
        
        # Tool Definition Cache (server_name -> list[tool])
        self.tool_cache: Dict[str, List[Any]] = {}
        
        self._initialized = True

    def whitelist_tool(self, tool_name: str):
        """Add a tool to the session whitelist to bypass HITL."""
        self.whitelisted_tools.add(tool_name)
        logger.info(f"Tool {tool_name} whitelisted for this session.")
        
    def load_config(self) -> Dict[str, Any]:
        """Load configuration from file."""
        if not os.path.exists(self.config_path):
            logger.warning(f"Config file {self.config_path} not found.")
            return {"mcp_servers": []}
            
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return {"mcp_servers": []}

    def reload_config(self):
        """Reload configuration from disk."""
        logger.info("Reloading MCP configuration...")
        self.config_data = self.load_config()
        # Invalidate tool cache on Deep Reload (API key changes etc.)
        self.tool_cache = {}
        return self.config_data
            
    async def initialize(self):
        """Initialize all enabled MCP servers using mcp-use."""
        logger.info("Initializing MCP Manager with mcp-use...")
        
        # Initialize the client
        self._mcp_client = MCPClient()
        
        self.config_data = self.load_config()
        servers = self.config_data.get("mcp_servers", [])
        
        init_tasks = []
        
        for server_config in servers:
            if not server_config.get("enabled", False):
                continue
            
            name = server_config.get("name")
            init_tasks.append(self.init_server(name, server_config))
            
        if init_tasks:
            await asyncio.gather(*init_tasks, return_exceptions=True)
            
    def _resolve_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve environment variables in configuration."""
        resolved = config.copy()
        
        # Resolve 'env' dictionary
        if "env" in resolved:
            env = resolved["env"].copy()
            for k, v in env.items():
                if isinstance(v, str) and v.startswith("${") and v.endswith("}"):
                    var_name = v[2:-1]
                    val = os.getenv(var_name)
                    if val:
                        env[k] = val
            resolved["env"] = env
            
        # Resolve 'headers' dictionary
        if "headers" in resolved:
            headers = resolved["headers"].copy()
            for k, v in headers.items():
                if isinstance(v, str) and v.startswith("${") and v.endswith("}"):
                    var_name = v[2:-1]
                    val = os.getenv(var_name)
                    if val:
                        headers[k] = val
            resolved["headers"] = headers
            
        # StdioConnector in mcp-use doesn't support 'cwd'
        if "cwd" in resolved:
            del resolved["cwd"]
            
        return resolved

    async def init_server(self, name: str, config: Dict[str, Any]):
        """Initialize a single MCP server."""
        if self._mcp_client is None:
            self._mcp_client = MCPClient()

        try:
            # Check if server is enabled
            if not config.get("enabled", False):
                return

            # Optimization: Skip if already connected
            if name in self.server_sessions:
                # logger.debug(f"Skipping re-init for active server: {name}")
                return

            # Resolve configuration
            server_config = self._resolve_config(config)

            # Windows compatibility for npx
            if os.name == 'nt' and server_config.get("command") == "npx":
                server_config["command"] = "npx.cmd"
            
            # Add server to client
            # mcp-use expects config to have specific keys depending on type
            # For stdio: command, args, env
            # For http: url (mapped to base_url maybe?), headers
            self._mcp_client.add_server(name, server_config)
            
            # Create and initialize session
            session = await self._mcp_client.create_session(name)
            
            self.server_sessions[name] = session
            logger.info(f"Initialized client for server: {name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize server {name}: {e}")

    async def cleanup(self):
        """Disconnect all servers."""
        if self._mcp_client:
            try:
                await self._mcp_client.close_all_sessions()
            except Exception:
                # Suppress "Attempted to exit cancel scope" from anyio/mcp-use
                pass
            self._mcp_client = None
        self.server_sessions.clear()

    def _create_args_schema(self, name: str, schema: Dict[str, Any]) -> Type[BaseModel]:
        """
        Dynamically create a Pydantic model from a JSON schema.
        Copied from ExpertFactory to support tool conversion logic here.
        """
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        
        fields = {}
        for field_name, field_info in properties.items():
            field_type = Any
            t = field_info.get("type")
            
            # Basic type mapping
            if t == "string":
                field_type = str
            elif t == "integer":
                field_type = int
            elif t == "boolean":
                field_type = bool
            elif t == "number":
                field_type = float
            elif t == "array":
                items = field_info.get("items", {})
                if not items or not isinstance(items, dict):
                    field_type = List[str]
                else:
                    item_type = items.get("type")
                    if not item_type:
                        if items.get("properties") or items.get("oneOf") or items.get("anyOf"):
                            # Ambiguous or complex item type, try to recurse if properties exist
                            if items.get("properties"):
                                try:
                                    nested_model = self._create_args_schema(f"{name}_{field_name}_Item", items)
                                    field_type = List[nested_model]
                                except Exception:
                                    field_type = List[dict]
                            else:
                                field_type = List[dict]
                        else:
                            field_type = List[str]
                    elif item_type == "integer":
                        field_type = List[int]
                    elif item_type == "boolean":
                        field_type = List[bool]
                    elif item_type == "number":
                        field_type = List[float]
                    elif item_type == "object":
                        if items.get("properties"):
                            try:
                                nested_model = self._create_args_schema(f"{name}_{field_name}_Item", items)
                                field_type = List[nested_model]
                            except Exception:
                                field_type = List[dict]
                        else:
                            field_type = List[dict]
                    else:
                        field_type = List[str]
            elif t == "object":
                if field_info.get("properties"):
                    try:
                        field_type = self._create_args_schema(f"{name}_{field_name}", field_info)
                    except Exception:
                        field_type = dict
                else:
                    field_type = dict
                
            description = field_info.get("description", "")
            
            # Determine default value
            if field_name in required:
                default = ...
            else:
                default = None
                
            fields[field_name] = (field_type, Field(default=default, description=description))
            
        # If no properties, return empty model
        if not fields:
            return create_model(f"{name}Schema")
            
        return create_model(f"{name}Schema", **fields)

    def _create_langchain_tool(self, tool: Any, server_name: str) -> StructuredTool:
        """Convert MCP tool to LangChain StructuredTool."""
        # Setup args schema
        args_schema = self._create_args_schema(tool.name, getattr(tool, "inputSchema", {}))
        
        # Create callable wrapper
        async def _make_run_func(s_name=server_name, t_name=tool.name):
            async def _run(**kwargs):
                # HITL Wrapper Logic
                await self._check_hitl_approval(t_name, kwargs)
                return await self.call_tool(t_name, kwargs, server_name=s_name)
            return _run

        return StructuredTool.from_function(
            name=tool.name,
            description=getattr(tool, "description", "") or "",
            func=None,
            # Use the helper to create the async wrapper
            coroutine=self._create_tool_coroutine(server_name, tool.name),
            args_schema=args_schema
        )

    def _create_tool_coroutine(self, server_name: str, tool_name: str):
        """Create the async function for the tool."""
        async def _run(**kwargs):
            # HITL Wrapper Logic
            await self._check_hitl_approval(tool_name, kwargs)
            return await self.call_tool(tool_name, kwargs, server_name=server_name)
        return _run

    async def get_tools_for_server(self, server_name: str) -> List[StructuredTool]:
        """Get tools for a specific server, converting to LangChain tools."""
        session = self.server_sessions.get(server_name)
        if not session:
            # Silent return or log warning
            return []
            
        try:
            # Get tools from session
            mcp_tools = await session.list_tools()
            
            # Load config to check for disabled tools
            full_config = self.load_config()
            server_config = next((s for s in full_config.get("mcp_servers", []) if s["name"] == server_name), {})
            disabled_tools = server_config.get("disabled_tools", [])
            
            langchain_tools = []
            for tool in mcp_tools:
                if tool.name in disabled_tools:
                    continue
                # Skip if disabled
                # (We also cache ALL tools, so we filter them later if retrieved from cache)
                # But here we just build the list.
                # ACTUALLY: We should cache ALL tools, then filter at return.
                
                # Convert to LangChain tool
                lc_tool = self._create_langchain_tool(tool, server_name)
                langchain_tools.append(lc_tool)
            
            # Store ALL tools in cache
            self.tool_cache[server_name] = langchain_tools
            
            # Return only enabled ones
            active_tools = [t for t in langchain_tools if t.name not in disabled_tools]
            return active_tools
            
        except Exception as e:
            logger.error(f"Error getting tools for {server_name}: {e}")
            return []

    async def _check_hitl_approval(self, tool_name: str, tool_args: dict):
        """
        Check if tool requires approval and trigger interrupt if so.
        Allows session-based whitelisting.
        """
        # 0. Check session whitelist first
        if tool_name in self.whitelisted_tools:
            return

        # 1. Load latest config (dynamic)
        config = self.load_config()
        hitl_config = config.get("hitl_config", {})
        
        if not hitl_config.get("enabled", False):
            return

        mode = hitl_config.get("mode", "denylist")
        sensitive_tools = hitl_config.get("sensitive_tools", [])
        approval_message = hitl_config.get("approval_message", "Approve execution?")
        
        # 2. Check if approval is needed
        requires_approval = False
        
        if mode == "all":
            requires_approval = True
        elif mode == "denylist":
            # Check if matches any pattern in sensitive_tools
            for pattern in sensitive_tools:
                if fnmatch.fnmatch(tool_name, pattern):
                    requires_approval = True
                    break
        elif mode == "allowlist":
            # Block everything UNLESS it matches safe_tools (not implemented fully in config yet, assuming opposite of deny)
            # For now, let's just stick to sensitive_tools as "requires approval"
            pass

        if requires_approval:
            # 3. Trigger Interrupt
            from langgraph.types import interrupt
            
            logger.info(f"Interrupting for HITL approval: {tool_name}")
            user_decision = interrupt({
                "event": "tool_approval_required",
                "tool_name": tool_name,
                "tool_args": tool_args,
                "message": approval_message
            })
            
            if isinstance(user_decision, dict) and user_decision.get("action") == "reject":
                 raise ValueError(f"User rejected execution of tool: {tool_name}")
            elif isinstance(user_decision, str) and user_decision.lower() in ["n", "no", "reject"]:
                 raise ValueError(f"User rejected execution of tool: {tool_name}")

    def toggle_tool(self, tool_name: str, enable: bool) -> str:
        """
        Enable or disable a specific tool by name.
        Updates mcp_config.json to persist the change.
        """
        config_data = self.load_config()
        servers = config_data.get("mcp_servers", [])
        
        target_server = None
        target_server_idx = -1
        
        # 1. Find which server has this tool
        # This requires checking the active sessions.
        # If the server is disabled, we can't really toggle its tools easily without loading it?
        # But we assume the server is active if we are listing tools.
        
        found_server_name = None
        
        # Check active sessions for the tool
        for s_name, session in self.server_sessions.items():
            # This is async, but we are inside a sync/async boundary challenge
            # We can't await here easily if this is called from sync code, 
            # BUT we will call this from async main, so it is fine if we make this async
            # However, for now, let's just rely on the config logic if possible.
            # To be safe and simple: We iterate active sessions to find the owner.
            # But list_tools() is async.
            pass

        # Simplified approach: We search for the tool in the config's disabled lists first?
        # Or we ask the user to provide server name? No, user just says /disable tool
        
        # We need to map tool -> server.
        # Let's iterate over sessions and check their cached tools if available?
        # Or just blindly add to all servers? No.
        
        # Strategy: Iterate all servers in config.
        # This is tricky without knowing the tool owner.
        # However, for the purpose of this task, we can assume unique tool names 
        # or just try to find it in active sessions.
        
        # Let's actually assume we can find it in active sessions.
        pass

    async def find_tool_owner(self, tool_name: str) -> Optional[str]:
        """Find which server owns a tool."""
        for name, session in self.server_sessions.items():
            try:
                tools = await session.list_tools()
                for t in tools:
                    if t.name == tool_name:
                        return name
            except Exception:
                continue
        return None

    async def toggle_tool_status(self, tool_name: str, enable: bool) -> str:
        """
        Async toggle tool.
        """
        server_name = await self.find_tool_owner(tool_name)
        if not server_name:
            # Maybe it's already disabled? 
            # Check config for any server having it in disabled_tools?
            # Hard to know owner if disabled. 
            # Fallback: Check config for presence in any disabled_tools list
            full_config = self.load_config()
            for s in full_config.get("mcp_servers", []):
                if tool_name in s.get("disabled_tools", []):
                    server_name = s["name"]
                    break
            
            if not server_name:
                return f"Tool '{tool_name}' not found in any active server or disabled list."

        # Now update config
        full_config = self.load_config()
        server_config = next((s for s in full_config.get("mcp_servers", []) if s["name"] == server_name), None)
        
        if not server_config:
             return f"Server configuration for '{server_name}' not found."
             
        disabled_list = server_config.get("disabled_tools", [])
        
        if enable:
            if tool_name in disabled_list:
                disabled_list.remove(tool_name)
                server_config["disabled_tools"] = disabled_list
                self._save_config(full_config)
                return f"Tool '{tool_name}' enabled."
            else:
                return f"Tool '{tool_name}' is already enabled."
        else:
            if tool_name not in disabled_list:
                disabled_list.append(tool_name)
                server_config["disabled_tools"] = disabled_list
                self._save_config(full_config)
                return f"Tool '{tool_name}' disabled. Restart/Reload required to apply?"
                # Actually, our list_tools logic filters based on config.
                # So next time get_tools_for_server is called (e.g. reload), it will be gone.
                # But existing agents might still have it? 
                # Yes, LangGraph agents are built at startup. 
                # So we DO need a reload or a live update.
                return f"Tool '{tool_name}' disabled. Run /reload to apply changes."
            else:
                return f"Tool '{tool_name}' is already disabled."

    def _save_config(self, config_data: dict):
        with open(self.config_path, 'w') as f:
            json.dump(config_data, f, indent=2)

    async def get_all_tools_status(self) -> Dict[str, Any]:
        """
        Get comprehensive status of all servers and tools.
        """
        status = {}
        full_config = self.load_config()
        
        for server in full_config.get("mcp_servers", []):
            s_name = server["name"]
            enabled = server.get("enabled", True)
            connected = s_name in self.server_sessions
            
            server_info = {
                "enabled": enabled,
                "connected": connected,
                "tools": []
            }
            
            if connected:
                # Get tools from session
                try:
                    session = self.server_sessions[s_name]
                    tools = await session.list_tools()
                    # Mark disabled ones
                    disabled_list = server.get("disabled_tools", [])
                    
                    for t in tools:
                        server_info["tools"].append({
                            "name": t.name,
                            "description": (getattr(t, "description", "") or "").split("\n")[0],
                            "active": t.name not in disabled_list
                        })
                except Exception as e:
                     server_info["error"] = str(e)
            
            status[s_name] = server_info
            
        return status


    async def call_tool(self, tool_name: str, arguments: dict, server_name: str = None) -> Any:
        """
        Call a tool. 
        If server_name is provided, use that session.
        Otherwise, scan sessions (slower/risky).
        """
        # --- Runtime Guard ---
        # Check if the tool is explicitly disabled in the config
        # This prevents use of tools that were disabled via CLI but might still be in the agent's context context
        config = self.load_config()
        for server in config.get("mcp_servers", []):
             if tool_name in server.get("disabled_tools", []):
                  logger.warning(f"Blocked attempt to use disabled tool: {tool_name}")
                  return f"Error: The tool '{tool_name}' is currently disabled by the administrator."
        
        session = None
        
        if server_name:
            session = self.server_sessions.get(server_name)
            if not session:
                 raise ValueError(f"Server {server_name} not found or not connected.")
        else:
            # Find strategy
            # Since we don't have a map...
            pass
            
        if not session:
             raise ValueError("server_name is required for call_tool")

        try:
            result = await session.call_tool(tool_name, arguments)
            return self._process_tool_result(result)
        except Exception as e:
            # Catch ALL exceptions and return as string to the LLM
            # This prevents the agent from crashing and allows it to self-correct
            error_msg = str(e)
            logger.error(f"Tool execution failed: {tool_name} - {error_msg}")
            return f"Error: Tool execution failed. {error_msg}\nPlease verify parameters and try again."

    def _process_tool_result(self, result: Any) -> Any:
        """Handle large outputs"""
        import base64
        import uuid
        LARGE_OUTPUT_THRESHOLD = 50000 
        
        # mcp-use result is CallToolResult
        if hasattr(result, 'content'):
             # It's an object
             content_list = getattr(result, 'content', [])
             processed = []
             
             for item in content_list:
                # item is TextContent or ImageContent
                if hasattr(item, 'type') and item.type == 'image':
                    data = getattr(item, 'data', "")
                    if len(data) > LARGE_OUTPUT_THRESHOLD:
                         # Save logic
                         filename = f"screenshot_{uuid.uuid4()}.png"
                         filepath = os.path.join("screenshots", filename)
                         os.makedirs("screenshots", exist_ok=True)
                         with open(filepath, "wb") as f:
                             f.write(base64.b64decode(data))
                         processed.append(f"[Image saved to {os.path.abspath(filepath)}]")
                    else:
                         processed.append("[Image data]")
                elif hasattr(item, 'text'):
                     processed.append(item.text)
                else:
                     processed.append(str(item))
             
             return "\n".join(processed)

        return str(result)
