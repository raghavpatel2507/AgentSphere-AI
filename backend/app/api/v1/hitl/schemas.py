"""
Pydantic schemas for HITL (Human-in-the-Loop) endpoints.
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from enum import Enum


class HITLStatus(str, Enum):
    """HITL request status."""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


# ============================================
# Request Schemas
# ============================================

class HITLDecisionRequest(BaseModel):
    """Request body for approving/rejecting HITL request."""
    reason: Optional[str] = Field(None, max_length=1000)


class ApproveAndWhitelistRequest(BaseModel):
    """Request body for approving and whitelisting a tool."""
    reason: Optional[str] = Field(None, max_length=1000)
    whitelist_duration: Optional[str] = Field(
        None, 
        description="Duration to whitelist: 'session', 'forever', or None for just this call"
    )


# ============================================
# Response Schemas
# ============================================

class HITLRequestResponse(BaseModel):
    """Response for a single HITL request."""
    id: UUID
    user_id: UUID
    conversation_id: UUID
    thread_id: Optional[str] = None
    tool_name: str
    tool_args: Dict[str, Any]
    server_name: str
    status: HITLStatus
    decision_at: Optional[datetime] = None
    decision_reason: Optional[str] = None
    created_at: datetime
    expires_at: Optional[datetime] = None
    is_expired: bool = False
    
    class Config:
        from_attributes = True


class HITLListResponse(BaseModel):
    """Response for listing HITL requests."""
    requests: List[HITLRequestResponse]
    total: int
    pending_count: int
