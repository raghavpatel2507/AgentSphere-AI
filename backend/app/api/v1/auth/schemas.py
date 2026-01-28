"""
Pydantic schemas for authentication endpoints.
"""

from typing import Optional
from pydantic import BaseModel, EmailStr, Field
from uuid import UUID
from datetime import datetime


# ============================================
# Request Schemas
# ============================================

class RegisterRequest(BaseModel):
    """Request body for user registration."""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: Optional[str] = Field(None, max_length=255)


class LoginRequest(BaseModel):
    """Request body for user login."""
    email: EmailStr
    password: str


class RefreshTokenRequest(BaseModel):
    """Request body for token refresh."""
    refresh_token: str


class UpdateProfileRequest(BaseModel):
    """Request body for updating user profile."""
    full_name: Optional[str] = Field(None, max_length=255)
    preferences: Optional[dict] = None


class UpdateHITLConfigRequest(BaseModel):
    """Request body for updating HITL configuration."""
    enabled: Optional[bool] = None
    mode: Optional[str] = Field(None, pattern="^(allowlist|denylist)$")
    sensitive_tools: Optional[list[str]] = None
    approval_message: Optional[str] = None


# ============================================
# Response Schemas
# ============================================

class TokenResponse(BaseModel):
    """Response containing JWT tokens."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds until access token expires


class UserResponse(BaseModel):
    """Response containing user information."""
    id: UUID
    email: str
    full_name: Optional[str] = None
    is_active: bool
    hitl_config: dict
    preferences: dict
    created_at: datetime
    last_login_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class MessageResponse(BaseModel):
    """Simple message response."""
    message: str
    success: bool = True
