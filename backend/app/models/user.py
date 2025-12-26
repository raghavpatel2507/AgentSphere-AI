"""
User model for authentication and user management.
"""

from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from datetime import datetime, timezone
import uuid

from backend.app.db import Base


class User(Base):
    """Represents a registered user of the application."""
    
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    
    # Tenant association (optional)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey('tenants.id'), nullable=True, index=True)
    
    is_active = Column(Boolean, default=True)
    
    # HITL Configuration per user
    hitl_config = Column(JSONB, default={
        "enabled": True, 
        "mode": "denylist", 
        "sensitive_tools": ["*google*", "*delete*", "*remove*", "*write*", "*-rm"],
        "approval_message": "Execution requires your approval."
    })
    
    # User preferences (UI settings, etc.)
    preferences = Column(JSONB, default={})
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    
    def __repr__(self):
        return f"<User {self.email}>"
