"""
OAuth routes for MCP service authentication.
Handles OAuth flows for Gmail, YouTube, Zoho, and other services.
"""

from typing import Optional, List
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from urllib.parse import urlencode
import httpx

from backend.app.dependencies import get_db, get_current_user
from backend.app.models.user import User
from backend.app.models.oauth_token import OAuthToken
from backend.app.core.auth import encrypt_value, decrypt_value
from backend.app.api.v1.auth.schemas import MessageResponse


router = APIRouter(prefix="/oauth", tags=["OAuth"])


# ============================================
# Schemas
# ============================================

class OAuthConfig(BaseModel):
    """OAuth configuration for a service."""
    auth_uri: str
    token_uri: str
    client_id: str
    client_secret: str
    scopes: List[str]
    redirect_uri: str


class AuthUrlResponse(BaseModel):
    """Response containing OAuth authorization URL."""
    auth_url: str
    service: str


class OAuthCallbackRequest(BaseModel):
    """Request body for OAuth callback."""
    code: str
    redirect_uri: str


class OAuthStatusResponse(BaseModel):
    """OAuth authentication status."""
    service: str
    authenticated: bool
    scopes: List[str] = []
    expires_at: Optional[datetime] = None


# ============================================
# Service Configurations
# ============================================

OAUTH_CONFIGS = {
    "gmail": {
        "auth_uri": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "scopes": ["https://www.googleapis.com/auth/gmail.modify"],
    },
    "youtube": {
        "auth_uri": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "scopes": [
            "https://www.googleapis.com/auth/youtube.readonly",
            "https://www.googleapis.com/auth/youtube.force-ssl",
        ],
    },
    "google-drive": {
        "auth_uri": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "scopes": ["https://www.googleapis.com/auth/drive"],
    },
    "zoho": {
        "auth_uri": "https://accounts.zoho.com/oauth/v2/auth",
        "token_uri": "https://accounts.zoho.com/oauth/v2/token",
        "scopes": ["ZohoCliq.Webhooks.CREATE", "ZohoMail.messages.ALL"],
    },
}


# ============================================
# Routes
# ============================================

@router.get("/{service}/auth-url", response_model=AuthUrlResponse)
async def get_auth_url(
    service: str,
    redirect_uri: str = Query(..., description="Frontend callback URL"),
    current_user: User = Depends(get_current_user),
):
    """
    Get OAuth authorization URL for a service.
    
    The frontend should redirect the user to this URL to start OAuth flow.
    """
    if service not in OAUTH_CONFIGS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown service: {service}. Supported: {list(OAUTH_CONFIGS.keys())}"
        )
    
    config = OAUTH_CONFIGS[service]
    
    # Build auth URL
    params = {
        "response_type": "code",
        "client_id": _get_client_id(service),
        "redirect_uri": redirect_uri,
        "scope": " ".join(config["scopes"]),
        "access_type": "offline",
        "prompt": "consent",
        "state": str(current_user.id),  # Include user ID in state
    }
    
    auth_url = f"{config['auth_uri']}?{urlencode(params)}"
    
    return AuthUrlResponse(auth_url=auth_url, service=service)


@router.post("/{service}/callback", response_model=MessageResponse)
async def handle_oauth_callback(
    service: str,
    request: OAuthCallbackRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Handle OAuth callback and exchange code for tokens.
    
    The frontend should call this after receiving the OAuth callback.
    """
    if service not in OAUTH_CONFIGS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown service: {service}"
        )
    
    config = OAUTH_CONFIGS[service]
    
    # Exchange code for tokens
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                config["token_uri"],
                data={
                    "code": request.code,
                    "client_id": _get_client_id(service),
                    "client_secret": _get_client_secret(service),
                    "redirect_uri": request.redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Token exchange failed: {response.text}"
                )
            
            token_data = response.json()
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to exchange code: {str(e)}"
        )
    
    # Calculate expiration
    expires_in = token_data.get("expires_in", 3600)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    
    # Check for existing token
    result = await db.execute(
        select(OAuthToken).where(
            OAuthToken.user_id == current_user.id,
            OAuthToken.service == service
        )
    )
    existing_token = result.scalar_one_or_none()
    
    if existing_token:
        # Update existing token
        existing_token.access_token = encrypt_value(token_data["access_token"])
        if token_data.get("refresh_token"):
            existing_token.refresh_token = encrypt_value(token_data["refresh_token"])
        existing_token.scopes = token_data.get("scope", "").split(" ")
        existing_token.expires_at = expires_at
        existing_token.token_uri = config["token_uri"]
    else:
        # Create new token
        oauth_token = OAuthToken(
            user_id=current_user.id,
            service=service,
            access_token=encrypt_value(token_data["access_token"]),
            refresh_token=encrypt_value(token_data.get("refresh_token", "")),
            token_uri=config["token_uri"],
            scopes=token_data.get("scope", "").split(" "),
            expires_at=expires_at,
        )
        db.add(oauth_token)
    
    await db.commit()
    
    return MessageResponse(message=f"Successfully authenticated with {service}")


@router.get("/{service}/status", response_model=OAuthStatusResponse)
async def get_oauth_status(
    service: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Check OAuth authentication status for a service.
    """
    result = await db.execute(
        select(OAuthToken).where(
            OAuthToken.user_id == current_user.id,
            OAuthToken.service == service
        )
    )
    token = result.scalar_one_or_none()
    
    if not token:
        return OAuthStatusResponse(
            service=service,
            authenticated=False,
        )
    
    return OAuthStatusResponse(
        service=service,
        authenticated=True,
        scopes=token.scopes or [],
        expires_at=token.expires_at,
    )


@router.delete("/{service}/revoke", response_model=MessageResponse)
async def revoke_oauth(
    service: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Revoke OAuth tokens for a service.
    """
    result = await db.execute(
        select(OAuthToken).where(
            OAuthToken.user_id == current_user.id,
            OAuthToken.service == service
        )
    )
    token = result.scalar_one_or_none()
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No OAuth token found for {service}"
        )
    
    await db.delete(token)
    await db.commit()
    
    return MessageResponse(message=f"OAuth token for {service} revoked")


@router.get("/services")
async def list_oauth_services():
    """
    List all supported OAuth services.
    """
    return {
        "services": list(OAUTH_CONFIGS.keys()),
        "details": {
            service: {"scopes": config["scopes"]}
            for service, config in OAUTH_CONFIGS.items()
        }
    }


# ============================================
# Helper Functions
# ============================================

def _get_client_id(service: str) -> str:
    """Get client ID for a service from environment."""
    import os
    
    env_mappings = {
        "gmail": "GOOGLE_CLIENT_ID",
        "youtube": "GOOGLE_CLIENT_ID",
        "google-drive": "GOOGLE_CLIENT_ID",
        "zoho": "ZOHO_CLIENT_ID",
    }
    
    env_key = env_mappings.get(service)
    if not env_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No client ID mapping for {service}"
        )
    
    client_id = os.getenv(env_key)
    if not client_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Missing environment variable: {env_key}"
        )
    
    return client_id


def _get_client_secret(service: str) -> str:
    """Get client secret for a service from environment."""
    import os
    
    env_mappings = {
        "gmail": "GOOGLE_CLIENT_SECRET",
        "youtube": "GOOGLE_CLIENT_SECRET",
        "google-drive": "GOOGLE_CLIENT_SECRET",
        "zoho": "ZOHO_CLIENT_SECRET",
    }
    
    env_key = env_mappings.get(service)
    if not env_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No client secret mapping for {service}"
        )
    
    client_secret = os.getenv(env_key)
    if not client_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Missing environment variable: {env_key}"
        )
    
    return client_secret
