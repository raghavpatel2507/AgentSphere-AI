"""
Pydantic schemas for tools management endpoints.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from uuid import UUID


# ============================================
# Request Schemas
# ============================================

class ToggleToolRequest(BaseModel):
    """Request body for enabling/disabling a tool."""
    enabled: bool


class HITLToolConfigRequest(BaseModel):
    """Request body for configuring HITL for specific tools."""
    tool_patterns: List[str] = Field(..., description="Tool name patterns to match")
    require_approval: bool = True


# ============================================
# Response Schemas
# ============================================

class ToolInfo(BaseModel):
    """Information about a single tool."""
    name: str
    description: Optional[str] = None
    server_name: str
    enabled: bool = True
    requires_approval: bool = False
    input_schema: Optional[Dict[str, Any]] = None

class ToggleHITLRequest(BaseModel):
    """Request body for toggling HITL on a tool."""
    hitl_enabled: bool


class ToolListResponse(BaseModel):
    """Response for listing tools."""
    tools: List[ToolInfo]
    total: int


class ServerToolsResponse(BaseModel):
    """Response for tools from a specific server."""
    server_name: str
    connected: bool
    tools: List[ToolInfo]
    error: Optional[str] = None
