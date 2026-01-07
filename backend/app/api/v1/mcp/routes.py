"""
MCP Server management routes.
Handles adding, removing, enabling/disabling MCP servers.
"""

import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.dependencies import get_db, get_current_user
from backend.app.models.user import User
from backend.app.models.mcp_server import MCPServerConfig
from backend.app.core.auth import encrypt_config, decrypt_config
from backend.app.api.v1.mcp.schemas import (
    AddServerRequest,
    UpdateServerRequest,
    MCPServerResponse,
    MCPServerListResponse,
    TestConnectionResponse,
)
from backend.app.api.v1.auth.schemas import MessageResponse


router = APIRouter(prefix="/mcp/servers", tags=["MCP Servers"])
logger = logging.getLogger(__name__)


def _mask_sensitive_config(config: dict) -> dict:
    """Mask sensitive values in config for response."""
    masked = config.copy()
    if "env" in masked:
        masked_env = {}
        for key, value in masked["env"].items():
            if any(s in key.upper() for s in ["KEY", "TOKEN", "SECRET", "PASSWORD"]):
                masked_env[key] = "***masked***"
            else:
                masked_env[key] = value
        masked["env"] = masked_env
    return masked


@router.get("/", response_model=MCPServerListResponse)
async def list_servers(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List all configured MCP servers for the current user.
    """
    from backend.app.core.mcp.pool import mcp_pool
    manager = await mcp_pool.get_manager(current_user.id)
    
    # Get live status from manager (includes connected status and tools)
    all_status = await manager.get_all_tools_status()
    
    # Get icons from registry for matching
    from backend.app.core.mcp.registry import SPHERE_REGISTRY
    registry_icons = {app.name: app.icon for app in SPHERE_REGISTRY}
    
    # Also fetch from DB for basic info (id, timestamps)
    result = await db.execute(
        select(MCPServerConfig).where(MCPServerConfig.user_id == current_user.id)
    )
    db_configs = result.scalars().all()
    
    server_responses = []
    for db_cfg in db_configs:
        status_info = all_status.get(db_cfg.name, {})
        
        # Prepare a "safe" version of the config for the UI list
        safe_config = {}
        try:
            full_config = decrypt_config(db_cfg.config)
            safe_config = {
                "command": full_config.get("command", "unknown"),
                "args": full_config.get("args", []),
                # Omit env and encrypted blobs
            }
        except:
            safe_config = {"command": "unknown", "args": []}

        server_responses.append(MCPServerResponse(
            id=db_cfg.id,
            name=db_cfg.name,
            enabled=db_cfg.enabled,
            connected=status_info.get("connected", False),
            config=safe_config,
            disabled_tools=db_cfg.disabled_tools or [],
            tools=status_info.get("tools", []),
            icon=registry_icons.get(db_cfg.name),
            created_at=db_cfg.created_at,
            updated_at=db_cfg.updated_at,
        ))
    
    return MCPServerListResponse(
        servers=server_responses,
        total=len(server_responses),
    )


@router.post("/", response_model=MCPServerResponse, status_code=status.HTTP_201_CREATED)
async def add_server(
    request: AddServerRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Add a new MCP server configuration.
    """
    """
    Add a new MCP server configuration.
    """
    from backend.app.core.mcp.pool import mcp_pool
    manager = await mcp_pool.get_manager(current_user.id)
    
    # Check if server with same name already exists
    # manager.add_server would overwrite, maybe we want to protect?
    # manager currently does upsert logic.
    # The existing route raised 409 Conflict.
    # Let's preserve that check strictly via DB for now, OR trust manager.
    
    # For consistency, let's use manager, but handle conflict if needed.
    # Actually, legacy logic checked DB.
    # Let's keep DB check for Conflict to match API contract.
    result = await db.execute(
        select(MCPServerConfig).where(
            MCPServerConfig.user_id == current_user.id,
            MCPServerConfig.name == request.name
        )
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Server '{request.name}' already exists"
        )

    # Create a temporary test session to validate config before saving
    from mcp_use.client import MCPClient
    test_client = MCPClient()
    try:
        # Use request.config directly for test
        test_session = await test_client.create_session("temp_test", request.config)
        # If we reach here, connection was successful
        # We don't need to list tools, just knowing it spawns is enough
    except Exception as e:
        logger.error(f"Failed to validate server {request.name} before adding: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to connect to server with provided config: {str(e)}"
        )
    finally:
        # Client cleanup handled by GC or explicit close if library supports it
        pass

    # Success -> Persist using Manager
    await manager.save_server_config(request.name, request.config)
    
    # Reload local cache
    await manager.initialize()
    
    # Fetch created to return response format (singular MCPServerResponse)
    result = await db.execute(
        select(MCPServerConfig).where(
            MCPServerConfig.user_id == current_user.id,
            MCPServerConfig.name == request.name
        )
    )
    server = result.scalar_one_or_none()
    
    if not server:
         raise HTTPException(status_code=500, detail="Server saved but not found")

    # Get live status for connected field (optional but helpful)
    all_status = await manager.get_all_tools_status()
    status_info = all_status.get(server.name, {})

    # Use registry icon if available
    from backend.app.core.mcp.registry import SPHERE_REGISTRY
    registry_icons = {app.name: app.icon for app in SPHERE_REGISTRY}

    return MCPServerResponse(
        id=server.id,
        name=server.name,
        enabled=server.enabled,
        connected=status_info.get("connected", False),
        config=_mask_sensitive_config(server.config),
        disabled_tools=server.disabled_tools or [],
        tools=status_info.get("tools", []),
        icon=registry_icons.get(server.name),
        created_at=server.created_at,
        updated_at=server.updated_at,
    )


@router.get("/{server_name}", response_model=MCPServerResponse)
async def get_server(
    server_name: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get details for a specific MCP server.
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
    
    return MCPServerResponse(
        id=server.id,
        name=server.name,
        enabled=server.enabled,
        config=_mask_sensitive_config(server.config),
        disabled_tools=server.disabled_tools or [],
        created_at=server.created_at,
        updated_at=server.updated_at,
    )


@router.patch("/{server_name}", response_model=MCPServerResponse)
async def update_server(
    server_name: str,
    request: UpdateServerRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update MCP server configuration.
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
    
    if request.config is not None:
        # Save will handle encryption
        await manager.save_server_config(server_name, request.config)
        # Refresh to get updated state
        result = await db.execute(
            select(MCPServerConfig).where(
                MCPServerConfig.user_id == current_user.id,
                MCPServerConfig.name == server_name
            )
        )
        server = result.scalar_one()
    
    if request.enabled is not None:
        server.enabled = request.enabled
    
    await db.commit()
    await db.refresh(server)
    
    return MCPServerResponse(
        id=server.id,
        name=server.name,
        enabled=server.enabled,
        config=_mask_sensitive_config(server.config),
        disabled_tools=server.disabled_tools or [],
        created_at=server.created_at,
        updated_at=server.updated_at,
    )


@router.delete("/{server_name}", response_model=MessageResponse)
async def remove_server(
    server_name: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Remove an MCP server configuration.
    """
    """
    Remove an MCP server configuration.
    """
    from backend.app.core.mcp.pool import mcp_pool
    manager = await mcp_pool.get_manager(current_user.id)
    
    success = await manager.remove_server(server_name)
    if not success:
        # Check if it was just not found or failed? 
        # manager.remove_server returns False if failed OR not found.
        # Minimal check:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Server '{server_name}' not found or failed to remove"
        )
    
    return MessageResponse(message=f"Server '{server_name}' removed successfully")


@router.post("/{server_name}/enable", response_model=MessageResponse)
async def enable_server(
    server_name: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Enable an MCP server.
    """
    from backend.app.core.mcp.pool import mcp_pool
    manager = await mcp_pool.get_manager(current_user.id)
    
    success = await manager.toggle_server_status(server_name, True)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Server '{server_name}' not found"
        )
    
    return MessageResponse(message=f"Server '{server_name}' enabled")


@router.post("/{server_name}/disable", response_model=MessageResponse)
async def disable_server(
    server_name: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Disable an MCP server.
    """
    from backend.app.core.mcp.pool import mcp_pool
    manager = await mcp_pool.get_manager(current_user.id)
    
    success = await manager.toggle_server_status(server_name, False)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Server '{server_name}' not found"
        )
    
    return MessageResponse(message=f"Server '{server_name}' disabled")


@router.post("/{server_name}/test", response_model=TestConnectionResponse)
async def test_server_connection(
    server_name: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Test connection to an MCP server.
    
    Attempts to connect and list available tools.
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
    
    try:
        # Import MCP pool for testing
        from backend.app.core.mcp.pool import mcp_pool
        
        manager = await mcp_pool.get_manager(current_user.id)
        
        # Establishing a persistent connection via restart_server
        # (This establishes the session in the manager instance used by the chat)
        await manager.restart_server(server_name)
        
        # Get live tool status (this will now be populated because we are connected)
        all_status = await manager.get_all_tools_status()
        status_info = all_status.get(server_name, {})
        
        if not status_info.get("connected"):
            # If restart didn't result in connection
            return TestConnectionResponse(
                success=False,
                message=f"Failed to connect to '{server_name}'",
                tools_count=0,
                tools=[]
            )

        tools = status_info.get("tools", [])
        tool_names = [t.get("name") for t in tools]
        
        return TestConnectionResponse(
            success=True,
            message=f"Successfully connected to '{server_name}'",
            tools_count=len(tool_names),
            tools=tool_names,
        )
    except Exception as e:
        logger.error(f"Test connection error for {server_name}: {e}", exc_info=True)
        return TestConnectionResponse(
            success=False,
            message=f"Failed to connect to '{server_name}': {str(e)}",
            error=str(e),
        )



