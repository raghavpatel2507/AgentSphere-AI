import asyncio
from typing import List, Any, Callable, Dict, Type, Optional, Union
from langchain_core.tools import Tool, StructuredTool
from pydantic import create_model, BaseModel, Field

def load_mcp_tools_sync(client_wrapper: Any) -> List[Tool]:
    """
    Dynamically loads tools from an MCP client wrapper and converts them to LangChain tools.
    Uses synchronous methods on the client wrapper to ensure thread safety via background loops.
    
    Args:
        client_wrapper: An instance of an MCP client wrapper (e.g., GmailMCPClient).
                        Must implement `list_tools_sync()` and `call_tool_sync()`.

    Returns:
        List[Tool]: A list of LangChain tools ready to be used by an agent.
    """
    lc_tools = []
    
    # List tools using the synchronous wrapper (which handles thread dispatch)
    mcp_tools = client_wrapper.list_tools_sync()
    
    for tool_meta in mcp_tools:
        tool_name = tool_meta.name
        tool_description = tool_meta.description or f"Tool {tool_name}"
        input_schema = tool_meta.inputSchema
        
        # Create Pydantic model for arguments dynamically
        # MCP inputSchema is a JSON Schema dictionary
        properties = input_schema.get("properties", {})
        required = input_schema.get("required", [])
        
        fields = {}
        for prop_name, prop_def in properties.items():
            prop_type = str
            if prop_def.get("type") == "integer":
                prop_type = int
            elif prop_def.get("type") == "boolean":
                prop_type = bool
            elif prop_def.get("type") == "number":
                prop_type = float
            elif prop_def.get("type") == "array":
                prop_type = list
            elif prop_def.get("type") == "object":
                prop_type = dict
                
            # Handle optional fields with nullable defaults
            if prop_name not in required:
                # Check if the default is null - if so, make it Optional
                default_value = prop_def.get("default")
                if default_value is None or default_value == "null":
                    # Use Optional type to allow None values
                    fields[prop_name] = (Optional[prop_type], Field(default=None, description=prop_def.get("description", "")))
                else:
                    fields[prop_name] = (prop_type, Field(default=default_value, description=prop_def.get("description", "")))
            else:
                fields[prop_name] = (prop_type, Field(..., description=prop_def.get("description", "")))
                
        # If no properties, use an empty model
        if not fields:
            ArgsModel = create_model(f"{tool_name}Args")
        else:
            ArgsModel = create_model(f"{tool_name}Args", **fields)

        # Define the synchronous runner with None filtering
        def _run_tool_sync(t_name=tool_name, **kwargs):
            # Filter out None values to avoid passing null to MCP tools
            filtered_kwargs = {k: v for k, v in kwargs.items() if v is not None}
            return client_wrapper.call_tool_sync(t_name, filtered_kwargs)

        # Define the asynchronous runner (wraps sync call in thread for now)
        async def _run_tool_async(t_name=tool_name, **kwargs):
            # Filter out None values to avoid passing null to MCP tools
            filtered_kwargs = {k: v for k, v in kwargs.items() if v is not None}
            # This runs the sync call (which submits to background thread) in a thread pool
            # to avoid blocking the main loop.
            return await asyncio.to_thread(client_wrapper.call_tool_sync, t_name, filtered_kwargs)

        lc_tool = StructuredTool.from_function(
            func=_run_tool_sync,
            coroutine=_run_tool_async,
            name=tool_name,
            description=tool_description,
            args_schema=ArgsModel
        )
        lc_tools.append(lc_tool)
        
    return lc_tools

