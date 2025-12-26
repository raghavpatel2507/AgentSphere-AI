"""
Message model for individual chat messages.
"""

from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from datetime import datetime, timezone
import uuid

from backend.app.db import Base


class Message(Base):
    """
    Represents a single message in a conversation.
    
    Messages can be from 'USER', 'ASSISTANT', 'SYSTEM', or 'TOOL'.
    """
    
    __tablename__ = "messages"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Foreign key to conversation
    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey('conversations.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    
    # Message data
    role = Column(
        SQLEnum('USER', 'ASSISTANT', 'SYSTEM', 'TOOL', name='message_role'),
        nullable=False
    )
    content = Column(Text, nullable=False)
    extra_metadata = Column('metadata', JSONB, default={})
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    
    def __repr__(self):
        return f"<Message {self.id} ({self.role})>"
