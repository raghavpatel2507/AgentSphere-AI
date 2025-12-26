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
    
    Note: This endpoint requires active connections to MCP servers.
    """
    # Get enabled servers
    result = await db.execute(
        select(MCPServerConfig).where(
            MCPServerConfig.user_id == current_user.id,
            MCPServerConfig.enabled == True
        )
    )
    servers = result.scalars().all()
    
    if not servers:
        return ToolListResponse(tools=[], total=0)
    
    all_tools = []
    hitl_patterns = (current_user.hitl_config or {}).get("sensitive_tools", [])
    
    try:
        from backend.app.services.mcp_service import MCPService
        
        mcp_service = MCPService(current_user.id)
        
        for server in servers:
            try:
                tools = await mcp_service.get_tools_for_server(server.name, server.config)
                disabled_tools = server.disabled_tools or []
                
                for tool in tools:
                    tool_name = tool.get("name", "unknown")
                    all_tools.append(ToolInfo(
                        name=tool_name,
                        description=tool.get("description"),
                        server_name=server.name,
                        enabled=tool_name not in disabled_tools,
                        requires_approval=_tool_matches_hitl_pattern(tool_name, hitl_patterns),
                        input_schema=tool.get("inputSchema"),
                    ))
            except Exception as e:
                # Log error but continue with other servers
                pass
    except ImportError:
        # MCPService not yet available, return empty
        pass
    
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
    result = await db.execute(
        select(MCPServerConfig).where(
            MCPServerConfig.user_id == current_user.id,
            MCPServerConfig.name == server_name
        )
    )
    server = result.scalar_one_or_none()
    
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Server '{server_name}' not found"
        )
    
    hitl_patterns = (current_user.hitl_config or {}).get("sensitive_tools", [])
    disabled_tools = server.disabled_tools or []
    
    try:
        from backend.app.services.mcp_service import MCPService
        
        mcp_service = MCPService(current_user.id)
        tools_data = await mcp_service.get_tools_for_server(server.name, server.config)
        
        tools = [
            ToolInfo(
                name=t.get("name", "unknown"),
                description=t.get("description"),
                server_name=server.name,
                enabled=t.get("name", "") not in disabled_tools,
                requires_approval=_tool_matches_hitl_pattern(t.get("name", ""), hitl_patterns),
                input_schema=t.get("inputSchema"),
            )
            for t in tools_data
        ]
        
        return ServerToolsResponse(
            server_name=server_name,
            connected=True,
            tools=tools,
        )
    except Exception as e:
        return ServerToolsResponse(
            server_name=server_name,
            connected=False,
            tools=[],
            error=str(e),
        )


@router.post("/{server_name}/{tool_name}/enable", response_model=MessageResponse)
async def enable_tool(
    server_name: str,
    tool_name: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Enable a specific tool on a server.
    """
    result = await db.execute(
        select(MCPServerConfig).where(
            MCPServerConfig.user_id == current_user.id,
            MCPServerConfig.name == server_name
        )
    )
    server = result.scalar_one_or_none()
    
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Server '{server_name}' not found"
        )
    
    disabled_tools = server.disabled_tools or []
    if tool_name in disabled_tools:
        disabled_tools.remove(tool_name)
        server.disabled_tools = disabled_tools
        await db.commit()
    
    return MessageResponse(message=f"Tool '{tool_name}' enabled")


@router.post("/{server_name}/{tool_name}/disable", response_model=MessageResponse)
async def disable_tool(
    server_name: str,
    tool_name: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Disable a specific tool on a server.
    """
    result = await db.execute(
        select(MCPServerConfig).where(
            MCPServerConfig.user_id == current_user.id,
            MCPServerConfig.name == server_name
        )
    )
    server = result.scalar_one_or_none()
    
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Server '{server_name}' not found"
        )
    
    disabled_tools = server.disabled_tools or []
    if tool_name not in disabled_tools:
        disabled_tools.append(tool_name)
        server.disabled_tools = disabled_tools
        await db.commit()
    
    return MessageResponse(message=f"Tool '{tool_name}' disabled")
