"""
Tools management routes.
Handles listing, enabling/disabling tools, and HITL configuration.
"""

import fnmatch
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.dependencies import get_db, get_current_user
from backend.app.models.user import User
from backend.app.models.mcp_server import MCPServerConfig
from backend.app.api.v1.tools.schemas import (
    ToggleToolRequest,
    ToggleHITLRequest,
    ToolInfo,
    ToolListResponse,
    ServerToolsResponse,
)
from backend.app.api.v1.auth.schemas import MessageResponse


router = APIRouter(prefix="/mcp/tools", tags=["MCP Tools"])


def _tool_matches_hitl_pattern(tool_name: str, patterns: List[str]) -> bool:
    """Check if tool name matches any HITL pattern."""
    for pattern in patterns:
        if fnmatch.fnmatch(tool_name.lower(), pattern.lower()):
            return True
    return False


@router.get("/", response_model=ToolListResponse)
async def list_all_tools(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List all available tools across enabled MCP servers.
    """
    from src.core.mcp.pool import mcp_pool
    manager = await mcp_pool.get_manager(current_user.id)
    
    all_status = await manager.get_all_tools_status()
    all_tools = []
    
    for server_name, status in all_status.items():
        for tool in status.get("tools", []):
            all_tools.append(ToolInfo(
                name=tool["name"],
                description=tool.get("description"),
                server_name=server_name,
                enabled=tool["enabled"],
                requires_approval=tool["hitl"],
                input_schema=None # manager doesn't cache schema yet, but could wrap
            ))
            
    return ToolListResponse(tools=all_tools, total=len(all_tools))


@router.get("/{server_name}", response_model=ServerToolsResponse)
async def get_server_tools(
    server_name: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List tools for a specific MCP server.
    """
    from src.core.mcp.pool import mcp_pool
    manager = await mcp_pool.get_manager(current_user.id)
    
    all_status = await manager.get_all_tools_status()
    server_status = all_status.get(server_name)
    
    if not server_status:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Server '{server_name}' not found or disconnected"
        )
    
    tools = [
        ToolInfo(
            name=t["name"],
            description=t.get("description"),
            server_name=server_name,
            enabled=t["enabled"],
            requires_approval=t["hitl"]
        )
        for t in server_status.get("tools", [])
    ]
    
    return ServerToolsResponse(
        server_name=server_name,
        connected=server_status["connected"],
        tools=tools,
    )


@router.post("/{server_name}/{tool_name}/toggle", response_model=MessageResponse)
async def toggle_tool(
    server_name: str,
    tool_name: str,
    request: ToggleToolRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Enable or disable a specific tool.
    """
    from src.core.mcp.pool import mcp_pool
    manager = await mcp_pool.get_manager(current_user.id)
    
    # Passing server_name to ensure we update the right server config
    message = await manager.toggle_tool_status(tool_name, request.enabled, server_name=server_name)
    return MessageResponse(message=message)


@router.post("/{server_name}/{tool_name}/hitl", response_model=MessageResponse)
async def toggle_tool_hitl(
    server_name: str,
    tool_name: str,
    request: ToggleHITLRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Toggle HITL requirement for a tool.
    """
    from src.core.mcp.pool import mcp_pool
    manager = await mcp_pool.get_manager(current_user.id)
    
    message = await manager.toggle_tool_hitl(tool_name, request.hitl_enabled)
    return MessageResponse(message=message)
