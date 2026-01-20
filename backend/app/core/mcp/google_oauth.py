"""
Google OAuth Handler - Generic OAuth flow for Google-based MCP integrations.

Handles OAuth authentication flow that:
1. Starts when user clicks "Connect Tools" in UI
2. Opens browser for Google authentication
3. Saves tokens to database (not local files)
4. Integrates with existing TokenManager
"""

import asyncio
import json
import webbrowser
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from urllib.parse import urlencode
import secrets
import logging

from aiohttp import web
from backend.app.core.mcp.token_manager import TokenManager
from backend.app.api.v1.oauth.pkce import generate_pkce

logger = logging.getLogger(__name__)


class GenericOAuthHandler:
    """Handles OAuth flow with database token storage for any provider (Cloud-Ready)."""
    
    def __init__(
        self,
        user_id: str,
        service_name: str,
        client_id: str,
        client_secret: str,
        authorization_url: str,
        token_url: str,
        redirect_uri: Optional[str] = None,
        scopes: list = [],
        use_pkce: bool = False
    ):
        self.user_id = user_id
        self.service_name = service_name
        self.client_id = client_id
        self.client_secret = client_secret
        self.authorization_url = authorization_url
        self.token_url = token_url
        self.scopes = scopes
        self.use_pkce = use_pkce
        self.token_manager = TokenManager(user_id)
        
        # Generate PKCE parameters if needed
        if self.use_pkce:
            self.code_verifier, self.code_challenge = generate_pkce()
            logger.info(f"🔐 Generated PKCE parameters for {service_name}")
        else:
            self.code_verifier = None
            self.code_challenge = None
        
        # dynamic import to avoid circular dep if config imported at top
        from backend.app.config import config
        self.redirect_uri = redirect_uri or f"{config.API_BASE_URL}/api/v1/mcp/oauth/callback"
        
    def get_authorization_url(self) -> str:
        """Generate OAuth authorization URL."""
        # State should encode the service name and user_id to survive the roundtrip
        # Simple format: "service_name:user_id:random"
        state_data = {
            "service": self.service_name,
            "user_id": str(self.user_id),
            "nonce": secrets.token_urlsafe(8)
        }
        state_str = json.dumps(state_data)
        import base64
        state_b64 = base64.urlsafe_b64encode(state_str.encode()).decode()
        
        # Detect if this is GitHub to use appropriate prompt parameter
        is_github = "github.com" in self.authorization_url.lower()
        
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.scopes),
            "state": state_b64,
            "access_type": "offline",  # Get refresh token
        }
        
        # GitHub-specific: Force account selection to ensure user isolation
        # This prevents auto-approval when user is already logged into GitHub
        if is_github:
            params["prompt"] = "select_account"
            logger.info(f"🔐 GitHub detected - forcing account selection for user isolation")
        else:
            # For other services (Google, etc.), force consent to get refresh token
            params["prompt"] = "consent"
        
        # Add PKCE parameters if enabled
        if self.use_pkce and self.code_challenge:
            params["code_challenge"] = self.code_challenge
            params["code_challenge_method"] = "S256"
            logger.info(f"🔐 Added PKCE challenge to authorization URL for {self.service_name}")
        
        return f"{self.authorization_url}?{urlencode(params)}"
    
    async def exchange_code(self, code: str) -> Dict[str, Any]:
        """Exchange authorization code for access and refresh tokens."""
        import aiohttp
        
        data = {
            "code": code,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
            "grant_type": "authorization_code"
        }
        
        # Add PKCE code_verifier if enabled
        if self.use_pkce and self.code_verifier:
            data["code_verifier"] = self.code_verifier
            logger.info(f"🔐 Added PKCE verifier to token exchange for {self.service_name}")
        
        # Some providers might need headers (Accept: application/json)
        headers = {"Accept": "application/json"}
        
        async with aiohttp.ClientSession() as session:
            async with session.post(self.token_url, data=data, headers=headers) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Token exchange failed: {error_text}")
                    raise Exception(f"Token exchange failed: {error_text}")
                
                # Check content type if it's not JSON (some providers return form-encoded)
                # But aiohttp.json() usually fails then.
                # GitHub returns form encoded unless Accept: application/json is sent
                
                token_response = await response.json()
                
                # Process and store tokens
                access_token = token_response.get("access_token")
                refresh_token = token_response.get("refresh_token")
                expires_in = token_response.get("expires_in", 3600)
                
                if not access_token:
                    raise Exception("No access token received from provider")
                
                logger.info(f"💾 Saving tokens for {self.service_name} to database...")
                await self.token_manager.store_token(
                    service=self.service_name,
                    access_token=access_token,
                    refresh_token=refresh_token,
                    token_uri=self.token_url,
                    scopes=self.scopes,
                    expires_in=expires_in
                )
                
                return {
                    "success": True,
                    "service": self.service_name,
                    "scopes": self.scopes
                }
