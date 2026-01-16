"""
Pydantic schemas for MCP server management endpoints.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime


# ============================================
# Request Schemas
# ============================================

class AddServerRequest(BaseModel):
    """Request body for adding a new MCP server."""
    name: str = Field(..., min_length=1, max_length=255)
    config: Dict[str, Any] = Field(..., description="Server configuration (command, args, env, etc.)")
    enabled: bool = True


class UpdateServerRequest(BaseModel):
    """Request body for updating server configuration."""
    config: Optional[Dict[str, Any]] = None
    enabled: Optional[bool] = None


class TestConnectionRequest(BaseModel):
    """Request body for testing server connection."""
    timeout_seconds: int = Field(30, ge=5, le=120)


# ============================================
# Response Schemas
# ============================================

class ToolStatus(BaseModel):
    """Status of a specific tool on a server."""
    name: str
    description: Optional[str] = None
    enabled: bool
    hitl: bool

class MCPServerResponse(BaseModel):
    """Response for a single MCP server."""
    id: UUID
    name: str
    enabled: bool
    connected: bool = False
    config: Optional[Dict[str, Any]] = None
    tools: List[ToolStatus] = []
    disabled_tools: List[str] = []
    created_at: datetime
    updated_at: datetime
    icon: Optional[str] = None
    status: Optional[str] = "Details unknown"
    tools_count: int = 0
    
    class Config:
        from_attributes = True


class MCPServerListResponse(BaseModel):
    """Response for listing MCP servers."""
    servers: List[MCPServerResponse]
    total: int


class TestConnectionResponse(BaseModel):
    """Response for connection test."""
    success: bool
    message: str
    tools_count: Optional[int] = None
    tools: Optional[List[str]] = None
    error: Optional[str] = None


class ToggleToolRequest(BaseModel):
    enabled: bool


class ToggleHITLRequest(BaseModel):
    hitl_enabled: bool


class ToolStatusResponse(BaseModel):
    message: str
    tool_name: str
    status: bool


class ServerStatusResponse(BaseModel):
    """Response for server status check."""
    name: str
    enabled: bool
    connected: bool
    tools_available: int = 0
    last_connected: Optional[datetime] = None
