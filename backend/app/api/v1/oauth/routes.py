from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException, Request
from fastapi.responses import RedirectResponse, JSONResponse
from backend.app.core.oauth.service import oauth_service
from backend.app.core.oauth.registry import get_provider
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.dependencies import get_current_user_optional, get_current_user, get_db
from backend.app.core.state.models import User
from backend.app.core.mcp.factory import build_mcp_config
import logging

router = APIRouter(prefix="/oauth", tags=["OAuth"])
logger = logging.getLogger(__name__)


@router.get("/{provider}/login")
async def login(
    provider: str,
    redirect_url: str = Query(..., description="Frontend URL to redirect back to"),
    target_app: Optional[str] = Query(None, description="Specific MCP App ID to configure"),
    server_url: Optional[str] = Query(None, description="Dynamic server URL (e.g. for Zoho)"),
    user: User = Depends(get_current_user)
):
    """
    Standard OAuth login entry point.
    If server_url is provided, it uses dynamic discovery (for Zoho etc).
    """
    user_id = str(user.id)
    
    try:
        if server_url:
            # Resolve any dynamic discovery (Zoho style)
            url = await oauth_service.start_dynamic_auth(user_id, server_url, redirect_url, target_app)
        else:
            # Standard static OAuth
            url = await oauth_service.start_auth(provider, user_id, redirect_url, target_app)
            
        return JSONResponse(content={"url": url})
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"OAuth Login error: {e}")
        raise HTTPException(status_code=500, detail="Failed to initiate login")


@router.get("/callback")
async def callback(
    state: str,
    code: str = None,
    error: str = None,
    error_description: str = None,
    db: AsyncSession = Depends(get_db)
):
    """
    OAuth Callback handler.
    Exchanges code for token and redirects user back to frontend.
    Auto-configures MCP servers (e.g., Gmail) if applicable.
    Handles errors by redirecting to frontend with error details.
    """
    # 1. Handle explicit errors from provider (e.g. access_denied)
    if error:
        # Try to retrieve frontend_url from state
        state_data = oauth_service.get_state_data(state)
        frontend_url = state_data.get("redirect_url") if state_data else "http://localhost:5173" # Fallback
        provider = state_data.get("provider") if state_data else None
        
        # Build query params
        query_params = {
            "status": "error",
            "error": error,
            "error_description": error_description or "Authentication failed"
        }
        if provider:
            query_params["provider"] = provider
            
        from urllib.parse import urlencode
        final_url = f"{frontend_url}?{urlencode(query_params)}"
        return RedirectResponse(url=final_url)

    # 2. Handle missing code
    if not code:
        return JSONResponse(status_code=400, content={"error": "Missing authorization code"})

    try:
        # 3. Exchange code for token
        frontend_url, user_id, provider_name, target_app = await oauth_service.exchange_code_dynamic(code, state)
        
        # -------------------------------------------------------------
        # Auto-Configure MCP Server based on provider
        # -------------------------------------------------------------
        from backend.app.core.mcp.registry import get_primary_app_for_provider
        
        # Prioritize target app (passed from frontend) or fallback to primary in registry
        target_app_id = target_app if target_app else get_primary_app_for_provider(provider_name)
        
        if target_app_id:
            # Import mcp_pool to get manager for this user
            from backend.app.core.mcp.pool import mcp_pool
            manager = await mcp_pool.get_manager(user_id)
            
            # Build configuration generically via factory
            resolved_config = await build_mcp_config(target_app_id, user_id)
            if resolved_config:
                await manager.save_server_config(target_app_id, resolved_config)
                logger.info(f"Auto-configured and started {target_app_id} for user {user_id}")

        # Append status=success
        from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
        
        # Parse frontend_url to handle existing params safely
        parsed = urlparse(frontend_url)
        params = parse_qs(parsed.query)
        
        params.update({
            "status": "success",
            "provider_connected": "true",
            "provider": provider_name
        })
        
        # Rebuild URL
        new_query = urlencode(params, doseq=True)
        final_url = urlunparse(parsed._replace(query=new_query))
        
        return RedirectResponse(url=final_url)
    except ValueError as e:
         return JSONResponse(status_code=400, content={"error": str(e)})
    except Exception as e:
        logger.error(f"Callback error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return JSONResponse(status_code=500, content={"error": "Internal Server Error"})
