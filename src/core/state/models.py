"""
Database models for conversations and messages.

This module defines the SQLAlchemy models for storing conversation history
in a normalized database schema (conversations and messages tables).
"""

from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Boolean, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from src.core.config.database import Base
from datetime import datetime, timezone
import uuid

# Import HITLRequest from backend to avoid duplication
# This allows MCPManager to query for approvals
try:
    from backend.app.models.hitl_request import HITLRequest
except ImportError:
    # Fallback if backend models aren't accessible
    HITLRequest = None


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


class User(Base):
    """
    Represents a registered user of the application.
    """
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    
    is_active = Column(Boolean, default=True)
    hitl_config = Column(JSONB, default={
        "enabled": True, 
        "mode": "denylist", 
        "sensitive_tools": ["*google*", "*delete*", "*remove*", "*write*", "*-rm"],
        "approval_message": "Execution requires your approval."
    })
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class MCPServerConfig(Base):
    """
    Stores configuration for an MCP server, specific to a user.
    Sensitive details (like tokens in 'env') can be encrypted.
    """
    __tablename__ = "mcp_server_configs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    
    name = Column(String(255), nullable=False)
    config = Column(JSONB, nullable=False) # The full config dict
    
    enabled = Column(Boolean, default=True)
    is_encrypted = Column(Boolean, default=False) # Flag to indicate if we need to decrypt
    
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

