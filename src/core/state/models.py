"""
Database models for conversations and messages.

This module defines the SQLAlchemy models for storing conversation history
in a normalized database schema (conversations and messages tables).
"""

from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from src.core.config.database import Base
from datetime import datetime, timezone
import uuid


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
    thread_id = Column(String, nullable=False, unique=True, index=True)  # Links to LangGraph
    title = Column(String(500))  # Auto-generated from first message
    status = Column(
        SQLEnum('ACTIVE', 'ARCHIVED', 'PENDING_APPROVAL', name='conversation_status'),
        default='ACTIVE',
        nullable=False
    )
    # Note: 'metadata' is reserved in SQLAlchemy, so we use 'extra_metadata' and map to 'metadata' column
    extra_metadata = Column('metadata', JSONB, default={})  # Additional metadata (tags, etc.)
    
    # Timestamps - use client-side default since DB doesn't have server default
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)


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
    # Note: 'metadata' is reserved in SQLAlchemy, so we use 'extra_metadata' and map to 'metadata' column
    extra_metadata = Column('metadata', JSONB, default={})  # Additional metadata (tool calls, etc.)
    
    # Timestamps - use client-side default since DB doesn't have server default
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

