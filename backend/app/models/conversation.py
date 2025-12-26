"""
Conversation model for chat threads.
"""

from sqlalchemy import Column, String, Boolean, DateTime, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from datetime import datetime, timezone
import uuid

from backend.app.db import Base


class Conversation(Base):
    """
    Represents a conversation thread.
    
    A conversation contains multiple messages and belongs to a user and tenant.
    Each conversation has a unique thread_id that links to LangGraph's state management.
    """
    
    __tablename__ = "conversations"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Foreign keys
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    # Conversation metadata
    thread_id = Column(String, nullable=False, unique=True, index=True)
    title = Column(String(500))
    status = Column(
        SQLEnum('ACTIVE', 'ARCHIVED', 'PENDING_APPROVAL', name='conversation_status'),
        default='ACTIVE',
        nullable=False
    )
    extra_metadata = Column('metadata', JSONB, default={})
    
    # Soft delete support
    is_deleted = Column(Boolean, default=False, index=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    
    def __repr__(self):
        return f"<Conversation {self.thread_id}>"
