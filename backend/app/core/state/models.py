"""
Database models for conversations and messages.

This module defines the SQLAlchemy models for storing conversation history
in a normalized database schema (conversations and messages tables).
"""

from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Boolean, UniqueConstraint, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from backend.app.db import Base
from datetime import datetime, timezone
import uuid
import enum

class MessageRole(str, enum.Enum):
    """Roles for messages in a conversation."""
    SYSTEM = "SYSTEM"
    USER = "USER"
    ASSISTANT = "ASSISTANT"
    TOOL = "TOOL"

class HITLStatus(str, enum.Enum):
    """Status for HITL approval requests."""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"

class ConversationStatus(str, enum.Enum):
    """Status for conversations."""
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    COMPLETED = "COMPLETED"
    DELETED = "DELETED"

class Tenant(Base):
    """Tenant model for multi-tenant support."""
    __tablename__ = "tenants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    api_key = Column(String(255), unique=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    is_active = Column(Boolean, default=True, index=True)
    extra_metadata = Column('metadata', JSONB, default={})

    def __repr__(self):
        return f"<Tenant {self.name}>"


class TenantConfig(Base):
    """Tenant configuration model for storing per-tenant settings."""
    __tablename__ = "tenant_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    config_key = Column(String(255), nullable=False)
    config_value = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<TenantConfig {self.config_key}>"


class Conversation(Base):
    """
    Represents a conversation thread.
    """
    __tablename__ = "conversations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    thread_id = Column(String, nullable=False, unique=True, index=True)
    title = Column(String(500))
    status = Column(SQLEnum(ConversationStatus, name="conversation_status", native_enum=True), default=ConversationStatus.ACTIVE, nullable=False)
    extra_metadata = Column('metadata', JSONB, default={})
    
    # Soft delete support
    is_deleted = Column(Boolean, default=False, index=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    def __repr__(self):
        return f"<Conversation {self.thread_id}>"


class Message(Base):
    """
    Represents a single message in a conversation.
    """
    __tablename__ = "messages"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey('conversations.id', ondelete='CASCADE'), nullable=False, index=True)
    role = Column(SQLEnum(MessageRole, name="message_role", native_enum=True), nullable=False)
    content = Column(Text, nullable=False)
    extra_metadata = Column('metadata', JSONB, default={})
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    def __repr__(self):
        return f"<Message {self.id} ({self.role})>"


class User(Base):
    """Represents a registered user of the application."""
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey('tenants.id'), nullable=True, index=True)
    is_active = Column(Boolean, default=True)
    hitl_config = Column(JSONB, default={
        "enabled": True, 
        "mode": "denylist", 
        "sensitive_tools": ["*google*", "*delete*", "*remove*", "*write*", "*-rm"],
        "approval_message": "Execution requires your approval."
    })
    preferences = Column(JSONB, default={})
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    last_login_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<User {self.email}>"


class MCPServerConfig(Base):
    """Stores configuration for an MCP server, specific to a user."""
    __tablename__ = "mcp_server_configs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    config = Column(JSONB, nullable=False)
    enabled = Column(Boolean, default=True)
    is_encrypted = Column(Boolean, default=False)
    disabled_tools = Column(JSONB, default=[])
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    def __repr__(self):
        return f"<MCPServerConfig {self.name}>"


class HITLRequest(Base):
    """Stores human-in-the-loop approval requests."""
    __tablename__ = "hitl_requests"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey('conversations.id', ondelete='CASCADE'), nullable=False, index=True)
    
    tool_name = Column(String(255), nullable=False)
    tool_args = Column(JSONB, nullable=False)
    server_name = Column(String(255), nullable=True)
    
    status = Column(SQLEnum(HITLStatus, name="hitl_status", native_enum=True), default=HITLStatus.PENDING, nullable=False)
    decision_at = Column(DateTime(timezone=True), nullable=True)
    decision_reason = Column(Text, nullable=True)
    
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    @property
    def is_expired(self) -> bool:
        """Check if the request has expired."""
        if not self.expires_at:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    def __repr__(self):
        return f"<HITLRequest {self.tool_name} ({self.status})>"


class OAuthToken(Base):
    """
    Stores OAuth tokens for MCP services that require OAuth authentication.
    """
    __tablename__ = "oauth_tokens"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    service = Column(String(50), nullable=False)
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=True)
    token_uri = Column(String(500), nullable=True)
    scopes = Column(JSONB, default=[])
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    
    __table_args__ = (
        UniqueConstraint('user_id', 'service', name='uq_user_service'),
    )

    @property
    def is_expired(self) -> bool:
        """Check if the access token has expired."""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    def __repr__(self):
        return f"<OAuthToken {self.service} for user {self.user_id}>"



