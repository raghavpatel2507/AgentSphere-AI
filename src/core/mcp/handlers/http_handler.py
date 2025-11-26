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
    Supports session-based authentication (like GitHub Copilot MCP).
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.url = config.get("url")
        self.session_id: Optional[str] = None
        self.client: Optional[httpx.AsyncClient] = None
        self.headers = {
            "Content-Type": "application/json",
            "User-Agent": "agent-sphere-ai/1.0"
        }
        
    async def connect(self):
        """Establish connection (initialize session)."""
        if not self.url:
            raise ValueError("URL is required for HTTP MCP server")
            
        # Configure headers from env/config
        env_vars = self.config.get("env", {})
        
        # Specific handling for GitHub Copilot MCP
        if "api.githubcopilot.com" in self.url:
            self.headers["X-MCP-Toolsets"] = "repos"
            # Try GITHUB_MCP_TOKEN first (as used in working client), then fall back to GITHUB_PERSONAL_ACCESS_TOKEN
            token = env_vars.get("GITHUB_MCP_TOKEN") or env_vars.get("GITHUB_PERSONAL_ACCESS_TOKEN")
            if token:
                # Handle env var substitution if not already done by manager
                if token.startswith("${") and token.endswith("}"):
                    token = os.getenv(token[2:-1])
                if token:
                    self.headers["Authorization"] = f"Bearer {token}"
                else:
                    raise ValueError(f"GitHub MCP token not found in environment variables")
        
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
            print(f"🔍 Payload: {json.dumps(payload, indent=2)}")
            logger.debug(f"Connecting to {self.url}")
            logger.debug(f"Headers: {safe_headers}")
            logger.debug(f"Payload: {json.dumps(payload, indent=2)}")
            
            response = await self.client.post(self.url, json=payload)
            
            # Log response for debugging
            print(f"🔍 Response Status: {response.status_code}")
            print(f"🔍 Response Headers: {dict(response.headers)}")
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
        
        # Get owner for schema injection
        env_vars = self.config.get("env", {})
        owner = env_vars.get("GITHUB_USERNAME")
        if owner and owner.startswith("${") and owner.endswith("}"):
            owner = os.getenv(owner[2:-1])
        
        # Convert to MCP Tool objects
        tools = []
        for t in tools_data:
            input_schema = t.get("inputSchema", {"type": "object", "properties": {}, "required": []})
            
            # Inject owner parameter with default value for GitHub tools (matching client.py)
            if "api.githubcopilot.com" in self.url and owner:
                if "properties" in input_schema and "owner" not in input_schema["properties"]:
                    input_schema["properties"]["owner"] = {
                        "type": "string",
                        "description": f"Repository owner (default: {owner})",
                        "default": owner
                    }
                    print(f"🔍 Added default owner '{owner}' to tool schema: {t.get('name')}")
            
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
            
        # Inject owner for GitHub if missing (matching client.py behavior)
        if "api.githubcopilot.com" in self.url:
            if "owner" not in arguments:
                # Try to find GITHUB_USERNAME in env
                env_vars = self.config.get("env", {})
                owner = env_vars.get("GITHUB_USERNAME")
                if owner:
                    # Handle env var substitution
                    if owner.startswith("${") and owner.endswith("}"):
                        owner = os.getenv(owner[2:-1])
                    if owner:
                        arguments = {**arguments, "owner": owner}
                        print(f"🔍 Auto-injected owner: {owner} for tool: {tool_name}")
                        logger.info(f"Auto-injected owner parameter: {owner}")

        payload = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
            },
        }
        
        response = await self.client.post(self.url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        if "error" in data:
            raise RuntimeError(f"Tool execution error: {data['error']}")
            
        result = data.get("result", {})
        if result.get("isError"):
             content = result.get("content", [{"text": "Unknown error"}])
             text = "".join([c.get("text", "") for c in content])
             raise RuntimeError(f"Tool execution failed: {text}")
             
        # Return the content
        content = result.get("content", [])
        
        # Debug: print full response for file reading tools
        if "file" in tool_name.lower() or "read" in tool_name.lower():
            print(f"🔍 Full API Response for {tool_name}:")
            print(f"🔍 Result: {json.dumps(result, indent=2)[:500]}...")
        
        if content and "text" in content[0]:
            try:
                # Try to parse as JSON if it looks like it
                return json.loads(content[0]["text"])
            except:
                return content[0]["text"]
        return result
