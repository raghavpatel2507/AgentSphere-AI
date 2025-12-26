"""
MCP Server Configuration model.
"""

from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from datetime import datetime, timezone
import uuid

from backend.app.db import Base


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
    config = Column(JSONB, nullable=False)
    
    enabled = Column(Boolean, default=True)
    is_encrypted = Column(Boolean, default=False)
    
    # Tool-level configuration
    disabled_tools = Column(JSONB, default=[])  # List of disabled tool names
    
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    
    def __repr__(self):
        return f"<MCPServerConfig {self.name}>"
