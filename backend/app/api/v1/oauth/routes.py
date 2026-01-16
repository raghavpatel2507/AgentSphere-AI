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

@router.get("/zoho/login")
async def zoho_login(
    redirect_url: str = Query(..., description="Frontend URL to redirect back to"),
    server_url: str = Query(..., description="Zoho MCP Server URL"),
    user: User = Depends(get_current_user)
):
    """
    Special OAuth login for Zoho with dynamic URL discovery.
    Unlike other providers, Zoho requires a user-provided MCP server URL.
    OAuth metadata is discovered from the server's .well-known endpoint.
    """
    user_id = str(user.id)
    
    logger.info(f"Zoho OAuth login initiated for user {user_id}")
    logger.info(f"Server URL: {server_url}")
    logger.info(f"Redirect URL: {redirect_url}")
    
    try:
        url = await oauth_service.start_dynamic_auth(
            user_id,
            server_url,
            redirect_url
        )
        logger.info(f"Zoho OAuth URL generated successfully")
        return {"url": url}
    except ValueError as e:
        logger.error(f"Zoho OAuth ValueError: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Zoho OAuth unexpected error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to initiate Zoho OAuth: {str(e)}")


@router.get("/{provider}/login")
async def login(
    provider: str,
    redirect_url: str = Query(..., description="Frontend URL to redirect back to"),
    user: User = Depends(get_current_user)
):
    # Check if provider exists
    if not get_provider(provider):
        raise HTTPException(status_code=404, detail="Provider not found")

    # Use authenticated user ID
    user_id = str(user.id)

    try:
        url = await oauth_service.start_auth(provider, user_id, redirect_url)
        # Return as JSON so frontend can redirect window.location
        return {"url": url} 
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))



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

    # 2. Handle missing code (should generally be covered by error check above)
    if not code:
        return JSONResponse(status_code=400, content={"error": "Missing authorization code"})

    try:
        # Use exchange_code_dynamic which handles both dynamic and static OAuth
        frontend_url, user_id, provider_name = await oauth_service.exchange_code_dynamic(code, state)
        
        # -------------------------------------------------------------
        # Auto-Configure MCP Server based on provider
        # -------------------------------------------------------------
        app_id_map = {
            "google": "gmail-mcp",
            "github": "github",
            "zoho": "zoho"  # Add Zoho
        }
        
        target_app_id = app_id_map.get(provider_name)
        
        if target_app_id:
            # Import mcp_pool to get manager for this user
            from backend.app.core.mcp.pool import mcp_pool
            manager = await mcp_pool.get_manager(user_id)
            
            # For Zoho, we need to get the server_url from token metadata
            if provider_name == "zoho":
                token_metadata = await oauth_service.get_token_metadata(user_id, "zoho")
                if token_metadata and token_metadata.get("_server_url"):
                    # Build Zoho config with the actual URL and token
                    zoho_config = {
                        "type": "sse",
                        "url": token_metadata["_server_url"],
                        "auth": token_metadata.get("access_token")
                    }
                    await manager.save_server_config(target_app_id, zoho_config)
                    logger.info(f"Auto-configured Zoho MCP for user {user_id}")
            else:
                # retrieve resolved config using factory for other providers
                resolved_config = await build_mcp_config(target_app_id, user_id)
                if resolved_config:
                    await manager.save_server_config(target_app_id, resolved_config)
                    logger.info(f"Auto-configured and started {target_app_id} for user {user_id}")

        # Append status=success
        # Use urlencode to be safe
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
         # If state matches, redirect with error
         # If we can't find state data (because exchange_code popped it and failed?), we might fall back
         # But usually exchange_code fails early.
         # Note: exchange_code pops the state. If it fails, we don't have frontend_url easily unless we peaked...
         # But exchange_code returns tuple.
         
         # Ideally we should peek state first or handle error inside.
         # For now, simplistic JSON error if exchange fails is okay, BUT user might see black screen if it was a redirect.
         # However, the most common error 'access_denied' is now handled above.
         return JSONResponse(status_code=400, content={"error": str(e)})
    except Exception as e:
        logger.error(f"Callback error: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal Server Error"})
