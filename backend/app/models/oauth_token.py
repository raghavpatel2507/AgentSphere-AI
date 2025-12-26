"""
OAuth Token model for storing per-user OAuth credentials.
"""

from sqlalchemy import Column, String, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from datetime import datetime, timezone
import uuid

from backend.app.db import Base


class OAuthToken(Base):
    """
    Stores OAuth tokens for MCP services that require OAuth authentication.
    
    Tokens are stored encrypted for security.
    """
    
    __tablename__ = "oauth_tokens"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    
    # Service identifier (gmail, youtube, zoho, google-drive, etc.)
    service = Column(String(50), nullable=False)
    
    # Encrypted tokens
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=True)
    token_uri = Column(String(500), nullable=True)
    
    # Token metadata
    scopes = Column(JSONB, default=[])
    expires_at = Column(DateTime(timezone=True), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Unique constraint: one token per user per service
    __table_args__ = (
        UniqueConstraint('user_id', 'service', name='uq_user_service'),
    )
    
    def __repr__(self):
        return f"<OAuthToken {self.service} for user {self.user_id}>"
    
    @property
    def is_expired(self) -> bool:
        """Check if the access token has expired."""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at
