
"""
OAuth Routes - Centralized handler for MCP service authentication.
Replaces legacy "local server" approach with standard OAuth redirection flow.
"""

import logging
import json
import base64
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.dependencies import get_db, get_current_user
from backend.app.models.user import User
from backend.app.core.mcp.registry import get_app_by_id
from backend.app.core.mcp.google_oauth import GenericOAuthHandler
from backend.app.config import config

router = APIRouter(prefix="/mcp/oauth", tags=["MCP OAuth"])
logger = logging.getLogger(__name__)

@router.get("/authorize/{service_name}")
async def authorize_service(
    service_name: str,
    current_user: User = Depends(get_current_user)
):
    """
    Generate OAuth Authorization URL for a specific service.
    Returns: { "url": "https://accounts.google.com/..." }
    """
    app_config = get_app_by_id(service_name)
    if not app_config:
        raise HTTPException(status_code=404, detail="Service not found")
        
    custom_oauth = app_config.config_template.get("custom_oauth")
    if not custom_oauth:
        raise HTTPException(status_code=400, detail="Service does not support OAuth")
        
    try:
        # Check if auth/token URLs are present
        if "authorization_url" not in custom_oauth or "token_url" not in custom_oauth:
             raise HTTPException(status_code=500, detail="Service OAuth configuration incomplete (missing URLs)")

        handler = GenericOAuthHandler(
            user_id=str(current_user.id),
            service_name=service_name,
            client_id=custom_oauth["client_id"],
            client_secret=custom_oauth["client_secret"],
            authorization_url=custom_oauth["authorization_url"],
            token_url=custom_oauth["token_url"],
            scopes=custom_oauth.get("scopes", []),
            use_pkce=custom_oauth.get("use_pkce", False)
        )
        
        auth_url = handler.get_authorization_url()
        return {"url": auth_url}
        
    except Exception as e:
        logger.error(f"Failed to generate auth URL: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/callback")
async def oauth_callback(
    code: str,
    state: str,
    error: str = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Handle OAuth callback from providers (Google, GitHub, etc.).
    """
    if error:
        return RedirectResponse(f"{config.APP_URL}/servers?error={error}")
        
    try:
        # Decode state (format: json base64 encoded)
        # Expected: {"service": "...", "user_id": "...", "nonce": "..."}
        state_json = base64.urlsafe_b64decode(state).decode()
        state_data = json.loads(state_json)
        
        service_name = state_data.get("service")
        user_id_str = state_data.get("user_id")
        
        if not service_name or not user_id_str:
            raise ValueError("Invalid state parameter")
            
        # Initialize handler to exchange code
        app_config = get_app_by_id(service_name)
        if not app_config:
             raise ValueError(f"Service {service_name} not found")
             
        custom_oauth = app_config.config_template.get("custom_oauth")
        
        handler = GenericOAuthHandler(
            user_id=user_id_str,
            service_name=service_name,
            client_id=custom_oauth["client_id"],
            client_secret=custom_oauth["client_secret"],
            authorization_url=custom_oauth["authorization_url"],
            token_url=custom_oauth["token_url"],
            scopes=custom_oauth.get("scopes", []),
            use_pkce=custom_oauth.get("use_pkce", False)
        )
        
        # Exchange code for token and save to DB
        await handler.exchange_code(code)
        
        # Redirect back to Frontend
        return RedirectResponse(f"{config.APP_URL}/servers?success={service_name}")
        
    except Exception as e:
        logger.error(f"Callback failed: {e}")
        return RedirectResponse(f"{config.APP_URL}/servers?error={str(e)}")
