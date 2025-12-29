"""
Pydantic schemas for chat endpoints.
"""

from typing import Optional, List, Any, Dict
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from enum import Enum


class StreamEventType(str, Enum):
    """Types of streaming events."""
    STATUS = "status"
    TOKEN = "token"
    TOOL_START = "tool_start"
    TOOL_END = "tool_end"
    APPROVAL_REQUIRED = "approval_required"
    ERROR = "error"
    DONE = "done"


# ============================================
# Request Schemas
# ============================================

class NewChatRequest(BaseModel):
    """Request body for creating a new chat."""
    title: Optional[str] = Field(None, max_length=500)
    initial_message: Optional[str] = None


class SendMessageRequest(BaseModel):
    """Request body for sending a message."""
    content: str = Field(..., min_length=1, max_length=32000)
    is_resume: bool = Field(False, description="True if resuming after HITL approval")
    
    # HITL approval continuation (optional)
    hitl_request_id: Optional[str] = None
    hitl_decision: Optional[str] = Field(None, pattern="^(approved|rejected)$")


class HITLApprovalRequest(BaseModel):
    """Request body for HITL approval inline with message."""
    request_id: UUID
    approved: bool
    reason: Optional[str] = None


# ============================================
# Response Schemas
# ============================================

class ChatResponse(BaseModel):
    """Response for new chat creation."""
    thread_id: str
    conversation_id: UUID
    title: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class StreamEvent(BaseModel):
    """A single streaming event."""
    type: StreamEventType
    content: Optional[str] = None
    tool: Optional[str] = None
    inputs: Optional[Dict[str, Any]] = None
    output: Optional[Any] = None
    request_id: Optional[str] = None
    tool_name: Optional[str] = None
    tool_args: Optional[Dict[str, Any]] = None
    final_response: Optional[str] = None
    message: Optional[str] = None


class MessageResponse(BaseModel):
    """Response for a single message."""
    id: UUID
    conversation_id: UUID
    role: str
    content: str
    metadata: Dict[str, Any] = {}
    created_at: datetime
    
    class Config:
        from_attributes = True


class ChatStatusResponse(BaseModel):
    """Response for chat status check."""
    thread_id: str
    is_processing: bool
    pending_approval: Optional[UUID] = None
    last_activity: Optional[datetime] = None
