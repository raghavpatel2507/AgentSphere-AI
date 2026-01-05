"""
Pydantic schemas for chat endpoints.
Updated for simplified HITL flow.
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


class ResumeRequest(BaseModel):
    """Request body for resuming chat after HITL approval."""
    decisions: List[Dict[str, Any]]
    # Example: [{"type": "approve"}] 
    # or [{"type": "edit", "edited_action": {"name": "...", "args": {...}}}]


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
    has_pending_approval: bool
    pending_tool_name: Optional[str] = None
    pending_tool_args: Optional[Dict[str, Any]] = None
    last_activity: Optional[datetime] = None
