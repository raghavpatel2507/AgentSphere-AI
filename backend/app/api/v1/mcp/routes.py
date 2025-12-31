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
from backend.app.core.auth import encrypt_value, decrypt_value, decrypt_config
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
    from src.core.mcp.pool import mcp_pool
    manager = await mcp_pool.get_manager(current_user.id)
    
    # Get live status from manager (includes connected status and tools)
    all_status = await manager.get_all_tools_status()
    
    # Also fetch from DB for basic info (id, timestamps)
    result = await db.execute(
        select(MCPServerConfig).where(MCPServerConfig.user_id == current_user.id)
    )
    db_configs = result.scalars().all()
    
    server_responses = []
    for db_cfg in db_configs:
        status_info = all_status.get(db_cfg.name, {})
        
        server_responses.append(MCPServerResponse(
            id=db_cfg.id,
            name=db_cfg.name,
            enabled=db_cfg.enabled,
            config=_mask_sensitive_config(db_cfg.config),
            disabled_tools=db_cfg.disabled_tools or [],
            tools=status_info.get("tools", []),
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
    from src.core.mcp.pool import mcp_pool
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

    # Use Manager to Add
    # Note: request.config contains sensitive data unencrypted. 
    # manager.add_server expects raw config and handles encryption.
    
    # We validate connection by default? Original logic didn't validate unless requested?
    # Original route saved then returned.
    # manager.add_server(validate=False) saves and connects.
    
    success = await manager.add_server(request.name, request.config, validate=False)
    
    if not success:
         raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add server"
        )
         
    # Fetch created to return response format
    # Or just construct response? 
    # Let's fetch to be safe and consistent with schemas
    result = await db.execute(
        select(MCPServerConfig).where(
            MCPServerConfig.user_id == current_user.id,
            MCPServerConfig.name == request.name
        )
    )
    server = result.scalar_one_or_none()
    
    if not server:
         raise HTTPException(status_code=500, detail="Server saved but not found")

    return MCPServerResponse(
        id=server.id,
        name=server.name,
        enabled=server.enabled,
        config=_mask_sensitive_config(server.config),
        disabled_tools=[],
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
        # Encrypt sensitive values
        config = request.config.copy()
        if "env" in config:
            encrypted_env = {}
            for key, value in config["env"].items():
                if any(s in key.upper() for s in ["KEY", "TOKEN", "SECRET", "PASSWORD"]):
                    encrypted_env[key] = encrypt_value(str(value)) if value else value
                    server.is_encrypted = True
                else:
                    encrypted_env[key] = value
            config["env"] = encrypted_env
        server.config = config
    
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
    from src.core.mcp.pool import mcp_pool
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
    from src.core.mcp.pool import mcp_pool
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
    from src.core.mcp.pool import mcp_pool
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
        # Decrypt config if needed before testing
        config = server.config
        if server.is_encrypted:
            config = decrypt_config(config)
            
        # Import MCP service for testing
        from backend.app.services.mcp_service import MCPService
        
        mcp_service = MCPService(current_user.id)
        tools_count = await mcp_service.test_server_connection(server_name, config)
        
        return TestConnectionResponse(
            success=True,
            message=f"Successfully connected to '{server_name}'",
            tools_count=tools_count,
        )
    except Exception as e:
        logger.error(f"Test connection error for {server_name}: {e}", exc_info=True)
        return TestConnectionResponse(
            success=False,
            message=f"Failed to connect to '{server_name}': {str(e)}",
            error=str(e),
        )


