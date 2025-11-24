import asyncio
from typing import List, Any, Dict, Type
from langchain_core.tools import StructuredTool
from pydantic import create_model, Field


def _map_json_schema_to_pytype(prop_def: dict):
    """Convert JSON schema definition to Python type (Gemini-safe)."""
    t = prop_def.get("type")

    if t == "string":
        return str
    if t == "integer":
        return int
    if t == "boolean":
        return bool
    if t == "number":
        return float
    if t == "object":
        return dict

    if t == "array":
        items = prop_def.get("items", {})

        # Gemini requires items.type – so we force it
        item_type = items.get("type", "string")

        if item_type == "integer":
            return List[int]
        if item_type == "boolean":
            return List[bool]
        if item_type == "number":
            return List[float]
        if item_type == "object":
            return List[dict]

        # Default fallback (SAFE for Gemini)
        return List[str]

    return str


def load_mcp_tools_sync(client_wrapper: Any) -> List[StructuredTool]:
    lc_tools = []
    mcp_tools = client_wrapper.list_tools_sync()

    for tool_meta in mcp_tools:
        tool_name = tool_meta.name
        tool_description = tool_meta.description or f"Tool {tool_name}"
        input_schema = tool_meta.inputSchema or {}

        properties = input_schema.get("properties", {})
        required = input_schema.get("required", [])

        fields = {}

        for prop_name, prop_def in properties.items():
            py_type = _map_json_schema_to_pytype(prop_def)

            if prop_name not in required:
                fields[prop_name] = (
                    py_type,
                    Field(default=None, description=prop_def.get("description", ""))
                )
            else:
                fields[prop_name] = (
                    py_type,
                    Field(..., description=prop_def.get("description", ""))
                )

        ArgsModel = create_model(f"{tool_name}Args", **fields) if fields else create_model(f"{tool_name}Args")

        def _run_tool_sync(t_name=tool_name, **kwargs):
            return client_wrapper.call_tool_sync(t_name, kwargs)

        async def _run_tool_async(t_name=tool_name, **kwargs):
            return await asyncio.to_thread(client_wrapper.call_tool_sync, t_name, kwargs)

        lc_tool = StructuredTool.from_function(
            func=_run_tool_sync,
            coroutine=_run_tool_async,
            name=tool_name,
            description=tool_description,
            args_schema=ArgsModel
        )

        lc_tools.append(lc_tool)

    return lc_tools
