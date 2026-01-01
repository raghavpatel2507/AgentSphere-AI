"""
Authentication routes.
Handles user registration, login, token refresh, and profile management.
"""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.dependencies import get_db, get_current_user
from backend.app.models.user import User
from backend.app.core.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
    get_password_hash,
)
from backend.app.api.v1.auth.schemas import (
    RegisterRequest,
    LoginRequest,
    RefreshTokenRequest,
    UpdateProfileRequest,
    UpdateHITLConfigRequest,
    TokenResponse,
    UserResponse,
    MessageResponse,
)
from backend.app.config import settings


router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Register a new user.
    
    Creates a new user account with the provided email and password.
    """
    # Check if user already exists
    result = await db.execute(select(User).where(User.email == request.email))
    existing_user = result.scalar_one_or_none()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists"
        )
    
    # Create new user
    hashed_password = get_password_hash(request.password)
    new_user = User(
        email=request.email,
        password_hash=hashed_password,
        full_name=request.full_name,
    )
    
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    return new_user


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Authenticate user and return JWT tokens.
    
    Returns access token (short-lived) and refresh token (long-lived).
    """
    # Find user by email
    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated"
        )
    
    # Update last login
    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()
    
    # Create tokens
    token_data = {"sub": str(user.id)}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Refresh access token using refresh token.
    
    Returns new access token and refresh token pair.
    """
    payload = decode_token(request.refresh_token)
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Verify user still exists and is active
    from uuid import UUID
    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()
    
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or deactivated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create new tokens
    token_data = {"sub": str(user.id)}
    access_token = create_access_token(token_data)
    new_refresh_token = create_refresh_token(token_data)
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(
    current_user: User = Depends(get_current_user)
):
    """
    Logout user.
    
    Note: In a production system, you would want to blacklist the token.
    For now, the client should discard the tokens.
    """
    # TODO: Implement token blacklisting with Redis or DB table
    return MessageResponse(message="Successfully logged out")


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user)
):
    """
    Get current user's profile.
    """
    return current_user


@router.patch("/me", response_model=UserResponse)
async def update_profile(
    request: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update current user's profile.
    """
    if request.full_name is not None:
        current_user.full_name = request.full_name
    
    if request.preferences is not None:
        current_user.preferences = request.preferences
    
    await db.commit()
    await db.refresh(current_user)
    
    return current_user


@router.get("/me/hitl-config")
async def get_hitl_config(
    current_user: User = Depends(get_current_user)
):
    """
    Get current user's HITL configuration.
    """
    return current_user.hitl_config


@router.patch("/me/hitl-config", response_model=MessageResponse)
async def update_hitl_config(
    request: UpdateHITLConfigRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update current user's HITL configuration.
    """
    current_config = current_user.hitl_config or {}
    
    if request.enabled is not None:
        current_config["enabled"] = request.enabled
    if request.mode is not None:
        current_config["mode"] = request.mode
    if request.sensitive_tools is not None:
        current_config["sensitive_tools"] = request.sensitive_tools
    if request.approval_message is not None:
        current_config["approval_message"] = request.approval_message
    
    current_user.hitl_config = current_config
    await db.commit()
    
    return MessageResponse(message="HITL configuration updated successfully")
