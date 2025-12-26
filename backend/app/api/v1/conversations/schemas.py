"""
Pydantic schemas for conversation endpoints.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from enum import Enum


class ConversationStatus(str, Enum):
    """Conversation status options."""
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"
    PENDING_APPROVAL = "PENDING_APPROVAL"


# ============================================
# Request Schemas
# ============================================

class UpdateTitleRequest(BaseModel):
    """Request body for updating conversation title."""
    title: str = Field(..., min_length=1, max_length=500)


class ConversationFilters(BaseModel):
    """Query filters for listing conversations."""
    status: Optional[ConversationStatus] = None
    include_deleted: bool = False
    search: Optional[str] = None


# ============================================
# Response Schemas
# ============================================

class ConversationListItem(BaseModel):
    """Conversation item for list view."""
    id: UUID
    thread_id: str
    title: str
    status: str
    message_count: int = 0
    last_message_preview: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    is_deleted: bool = False
    
    class Config:
        from_attributes = True


class MessageSummary(BaseModel):
    """Brief message summary."""
    id: UUID
    role: str
    content: str
    created_at: datetime


class ConversationDetail(BaseModel):
    """Full conversation details with messages."""
    id: UUID
    thread_id: str
    title: str
    status: str
    metadata: Dict[str, Any] = {}
    messages: List[MessageSummary] = []
    created_at: datetime
    updated_at: datetime
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class ConversationListResponse(BaseModel):
    """Paginated list of conversations."""
    items: List[ConversationListItem]
    total: int
    page: int
    page_size: int
    has_more: bool
