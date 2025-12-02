import os
import json
import logging
import httpx
from typing import List, Dict, Any, Optional
from .base import MCPHandler
from mcp.types import Tool

logger = logging.getLogger(__name__)

class HttpMCPHandler(MCPHandler):
    """
    Handler for Remote MCP servers using JSON-RPC over HTTP.
    Supports generic headers and tool default injection via config.
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.url = config.get("url")
        self.session_id: Optional[str] = None
        self.client: Optional[httpx.AsyncClient] = None
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "User-Agent": "agent-sphere-ai/1.0"
        }
        
    async def connect(self):
        """Establish connection (initialize session)."""
        if not self.url:
            raise ValueError("URL is required for HTTP MCP server")
            
        # Configure headers from config
        config_headers = self.config.get("headers", {})
        env_vars = self.config.get("env", {})
        
        for key, value in config_headers.items():
            # Handle env var substitution
            if isinstance(value, str) and "${" in value:
                # Simple substitution for ${VAR}
                for env_key, env_val in env_vars.items():
                    # Also check actual os.environ if env_vars has placeholders
                    if env_val.startswith("${") and env_val.endswith("}"):
                        env_val = os.getenv(env_val[2:-1]) or ""
                    
                    if env_val:
                        value = value.replace(f"${{{env_key}}}", env_val)
                
                # Also try direct substitution from os.environ if not found in env_vars
                import re
                matches = re.findall(r"\$\{([A-Za-z0-9_]+)\}", value)
                for match in matches:
                    env_val = os.getenv(match)
                    if env_val:
                        value = value.replace(f"${{{match}}}", env_val)
            
            self.headers[key] = value
        
        self.client = httpx.AsyncClient(headers=self.headers, timeout=30.0)
        
        try:
            # Initialize Session
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "clientInfo": {
                        "name": "agent-sphere-ai",
                        "version": "1.0.0"
                    },
                    "capabilities": {"tools": {}},
                },
            }
            
            # Debug logging
            safe_headers = self.headers.copy()
            if "Authorization" in safe_headers:
                token_preview = safe_headers["Authorization"].split()[-1][:10] if len(safe_headers["Authorization"].split()) > 1 else "[INVALID]"
                safe_headers["Authorization"] = f"Bearer {token_preview}..."
            print(f"🔍 Connecting to {self.url}")
            print(f"🔍 Headers: {safe_headers}")
            # print(f"🔍 Payload: {json.dumps(payload, indent=2)}")
            logger.debug(f"Connecting to {self.url}")
            logger.debug(f"Headers: {safe_headers}")
            logger.debug(f"Payload: {json.dumps(payload, indent=2)}")
            
            response = await self.client.post(self.url, json=payload)
            
            # Log response for debugging
            print(f"🔍 Response Status: {response.status_code}")
            # print(f"🔍 Response Headers: {dict(response.headers)}")
            if response.status_code != 200:
                print(f"🔍 Response Body: {response.text}")
            
            response.raise_for_status()
            data = response.json()
            
            # Extract Session ID
            self.session_id = (
                response.headers.get("Mcp-Session-Id") or
                response.headers.get("mcp-session-id") or
                data.get("result", {}).get("sessionId")
            )
            
            if not self.session_id:
                logger.warning(f"No session ID received from {self.url}")
            else:
                logger.info(f"Connected to {self.name} with session ID: {self.session_id}")
            
            # Send 'initialized' notification to complete handshake
            # This is required by the MCP protocol after initialize succeeds
            initialized_payload = {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {}
            }
            
            headers_with_session = self.headers.copy()
            if self.session_id:
                headers_with_session["Mcp-Session-Id"] = self.session_id
            
            # Send notification (no response expected for notifications)
            await self.client.post(self.url, json=initialized_payload, headers=headers_with_session)
            logger.debug(f"Sent 'initialized' notification to {self.name}")
                
        except Exception as e:
            logger.error(f"Failed to connect to {self.name}: {e}")
            await self.disconnect()
            raise

    async def disconnect(self):
        """Close HTTP client."""
        if self.client:
            await self.client.aclose()
            self.client = None
        self.session_id = None

    async def list_tools(self) -> List[Tool]:
        """List available tools."""
        if not self.client:
            raise RuntimeError("Not connected")
            
        headers = self.headers.copy()
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
            
        payload = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        }
        
        response = await self.client.post(self.url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        if "error" in data:
            raise RuntimeError(f"Error listing tools: {data['error']}")
            
        tools_data = data.get("result", {}).get("tools", [])
        
        # Get tool defaults from config
        tool_defaults = self.config.get("tool_defaults", {})
        env_vars = self.config.get("env", {})
        
        # Resolve env vars in defaults
        resolved_defaults = {}
        for k, v in tool_defaults.items():
            if isinstance(v, str) and "${" in v:
                 # Simple substitution for ${VAR}
                for env_key, env_val in env_vars.items():
                    if env_val.startswith("${") and env_val.endswith("}"):
                        env_val = os.getenv(env_val[2:-1]) or ""
                    if env_val:
                        v = v.replace(f"${{{env_key}}}", env_val)
                
                import re
                matches = re.findall(r"\$\{([A-Za-z0-9_]+)\}", v)
                for match in matches:
                    env_val = os.getenv(match)
                    if env_val:
                        v = v.replace(f"${{{match}}}", env_val)
            resolved_defaults[k] = v
        
        # Convert to MCP Tool objects
        tools = []
        for t in tools_data:
            input_schema = t.get("inputSchema", {"type": "object", "properties": {}, "required": []})
            
            # Inject defaults into schema
            if resolved_defaults:
                if "properties" not in input_schema:
                    input_schema["properties"] = {}
                
                for param, default_val in resolved_defaults.items():
                    if param not in input_schema["properties"]:
                        input_schema["properties"][param] = {
                            "type": "string",
                            "description": f"Default parameter (injected): {default_val}",
                            "default": default_val
                        }
                        print(f"🔍 Added default parameter '{param}' to tool schema: {t.get('name')}")
            
            tools.append(Tool(
                name=t.get("name"),
                description=t.get("description"),
                inputSchema=input_schema
            ))
            
        return tools

    async def call_tool(self, tool_name: str, arguments: dict) -> Any:
        """Call a tool."""
        if not self.client:
            raise RuntimeError("Not connected")
            
        headers = self.headers.copy()
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
            
        # Inject defaults if missing
        tool_defaults = self.config.get("tool_defaults", {})
        env_vars = self.config.get("env", {})
        
        for param, default_val in tool_defaults.items():
            if param not in arguments:
                # Resolve env var if needed (repeating logic for safety, though list_tools does it too)
                if isinstance(default_val, str) and "${" in default_val:
                     for env_key, env_val in env_vars.items():
                        if env_val.startswith("${") and env_val.endswith("}"):
                            env_val = os.getenv(env_val[2:-1]) or ""
                        if env_val:
                            default_val = default_val.replace(f"${{{env_key}}}", env_val)
                     import re
                     matches = re.findall(r"\$\{([A-Za-z0-9_]+)\}", default_val)
                     for match in matches:
                        env_val = os.getenv(match)
                        if env_val:
                            default_val = default_val.replace(f"${{{match}}}", env_val)
                
                arguments[param] = default_val
                print(f"🔍 Auto-injected parameter: {param}={default_val} for tool: {tool_name}")
                logger.info(f"Auto-injected parameter: {param}")

        payload = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
            },
        }
        
        try:
            response = await self.client.post(self.url, json=payload, headers=headers)
            
            # Handle HTTP errors gracefully
            if response.status_code != 200:
                error_msg = f"HTTP Error {response.status_code}: {response.text}"
                logger.error(f"Tool call failed: {error_msg}")
                return f"Error: {error_msg}"
                
            data = response.json()
            
            if "error" in data:
                return f"Error: MCP Protocol Error: {data['error']}"
                
            result = data.get("result", {})
            
            # Handle Tool execution errors gracefully
            if result.get("isError"):
                 content = result.get("content", [{"text": "Unknown error"}])
                 text = "".join([c.get("text", "") for c in content])
                 return f"Error: Tool execution failed: {text}"
                 
            # Return the content
            content = result.get("content", [])
            
            # Debug: print full response for file reading tools
            if "file" in tool_name.lower() or "read" in tool_name.lower():
                print(f"🔍 Full API Response for {tool_name}:")
                print(f"🔍 Result: {json.dumps(result, indent=2)[:500]}...")
            
            # if content and "text" in content[0]:
            #     try:
            #         # Try to parse as JSON if it looks like it
            #         return json.loads(content[0]["text"])
            #     except:
            #         return content[0]["text"]
            # return result
            return content
            
        except Exception as e:
            logger.error(f"Unexpected error calling tool {tool_name}: {e}")
            return f"Error: Unexpected exception: {str(e)}"
