"""
MCP Server management routes.
Handles adding, removing, enabling/disabling MCP servers.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.dependencies import get_db, get_current_user
from backend.app.models.user import User
from backend.app.models.mcp_server import MCPServerConfig
from backend.app.core.auth import encrypt_value, decrypt_value
from backend.app.api.v1.mcp.schemas import (
    AddServerRequest,
    UpdateServerRequest,
    MCPServerResponse,
    MCPServerListResponse,
    TestConnectionResponse,
)
from backend.app.api.v1.auth.schemas import MessageResponse


router = APIRouter(prefix="/mcp/servers", tags=["MCP Servers"])


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
    result = await db.execute(
        select(MCPServerConfig).where(MCPServerConfig.user_id == current_user.id)
    )
    servers = result.scalars().all()
    
    server_responses = []
    for server in servers:
        server_responses.append(MCPServerResponse(
            id=server.id,
            name=server.name,
            enabled=server.enabled,
            config=_mask_sensitive_config(server.config),
            disabled_tools=server.disabled_tools or [],
            created_at=server.created_at,
            updated_at=server.updated_at,
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
    # Check if server with same name already exists
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
    
    # Encrypt sensitive values in config
    config = request.config.copy()
    is_encrypted = False
    if "env" in config:
        encrypted_env = {}
        for key, value in config["env"].items():
            if any(s in key.upper() for s in ["KEY", "TOKEN", "SECRET", "PASSWORD"]):
                encrypted_env[key] = encrypt_value(str(value)) if value else value
                is_encrypted = True
            else:
                encrypted_env[key] = value
        config["env"] = encrypted_env
    
    server = MCPServerConfig(
        user_id=current_user.id,
        name=request.name,
        config=config,
        enabled=request.enabled,
        is_encrypted=is_encrypted,
    )
    
    db.add(server)
    await db.commit()
    await db.refresh(server)
    
    return MCPServerResponse(
        id=server.id,
        name=server.name,
        enabled=server.enabled,
        config=_mask_sensitive_config(request.config),  # Return original masked
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
    
    await db.delete(server)
    await db.commit()
    
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
    
    server.enabled = True
    await db.commit()
    
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
    
    server.enabled = False
    await db.commit()
    
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
        # Import MCP service for testing
        from backend.app.services.mcp_service import MCPService
        
        mcp_service = MCPService(current_user.id)
        tools_count = await mcp_service.test_server_connection(server_name, server.config)
        
        return TestConnectionResponse(
            success=True,
            message=f"Successfully connected to '{server_name}'",
            tools_count=tools_count,
        )
    except Exception as e:
        return TestConnectionResponse(
            success=False,
            message=f"Failed to connect to '{server_name}'",
            error=str(e),
        )
