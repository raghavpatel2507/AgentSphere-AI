"""
HITL (Human-in-the-Loop) Request model for pending approvals.
"""

from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from datetime import datetime, timezone
import uuid

from backend.app.db import Base


class HITLRequest(Base):
    """
    Represents a pending HITL approval request.
    
    When an agent attempts to execute a sensitive tool, a request is created
    and the execution is paused until the user approves or rejects.
    """
    
    __tablename__ = "hitl_requests"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    
    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey('conversations.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    
    # Tool information
    tool_name = Column(String(255), nullable=False)
    tool_args = Column(JSONB, nullable=False)
    server_name = Column(String(255), nullable=False)
    
    # Request status
    status = Column(
        SQLEnum('PENDING', 'APPROVED', 'REJECTED', 'EXPIRED', name='hitl_status'),
        default='PENDING',
        nullable=False,
        index=True
    )
    
    # Decision metadata
    decision_at = Column(DateTime(timezone=True), nullable=True)
    decision_reason = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    
    def __repr__(self):
        return f"<HITLRequest {self.id} ({self.status})>"
    
    @property
    def is_expired(self) -> bool:
        """Check if the request has expired."""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at
