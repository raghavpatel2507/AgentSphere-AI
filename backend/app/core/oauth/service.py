import logging
import json
import secrets
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.mcp.registry import get_oauth_config_by_provider
from backend.app.core.oauth.pkce import generate_pkce
from backend.app.core.state.models import OAuthToken, User
from backend.app.config import config
from backend.app.db import AsyncSessionLocal

logger = logging.getLogger(__name__)

# Simple in-memory cache for PKCE/State (Redis is better for production)
# Structure: { "state_string": { "verifier": "...", "provider": "...", "user_id": "...", "redirect_url": "..." } }
AUTH_CACHE: Dict[str, Dict[str, str]] = {}

class OAuthService:

    async def start_auth(self, app_id: str, user_id: str, redirect_url_frontend: str, target_app: Optional[str] = None) -> str:
        """
        Generates the authorization URL.
        First tries to resolve app_id to a specific MCP app config.
        Falls back to treating app_id as a generic provider name.
        If target_app is provided, it takes precedence for config lookup.
        """
        oauth_config = None
        final_target_app = target_app
        
        # 1. Try to find specific app (Target App takes precedence)
        from backend.app.core.mcp.registry import get_app_by_id
        
        # If target_app provided, try that first
        if target_app:
            app = get_app_by_id(target_app)
            if app and app.oauth_config:
                oauth_config = app.oauth_config
                logger.info(f"Using OAuth config from target app '{target_app}' with scopes: {oauth_config.scopes}")
                
        # If no target_app or not found, try app_id
        if not oauth_config:
            app = get_app_by_id(app_id)
            if app and app.oauth_config:
                final_target_app = app_id
                oauth_config = app.oauth_config
                logger.info(f"Using OAuth config from app_id '{app_id}' with scopes: {oauth_config.scopes}")
        
        # 2. Fallback to generic provider lookup
        provider_name = app_id # Default assumption
        if not oauth_config:
            # Try to see if app_id is actually a provider name
            oauth_config = get_oauth_config_by_provider(app_id)
            if oauth_config:
                 provider_name = oauth_config.provider_name
        
        if not oauth_config:
            raise ValueError(f"No OAuth configuration found for '{app_id}'")

        # Use provider name from config if available (authoritative)
        if hasattr(oauth_config, "provider_name"):
            provider_name = oauth_config.provider_name

        # Check for static credentials
        client_id_var = getattr(oauth_config, "client_id_env", None)
        static_client_id = oauth_config.client_id or (client_id_var and getattr(config, client_id_var, None))

        # Dynamic Auth Delegation: If we have discovery URL but no static credentials, go dynamic
        if getattr(oauth_config, "discovery_url", None) and not static_client_id:
            logger.info(f"Delegating to Dynamic Auth for {provider_name} (No static creds, found discovery URL)")
            return await self.start_dynamic_auth(user_id, oauth_config.discovery_url, redirect_url_frontend, target_app)

        client_id = static_client_id
        if not client_id:
             # Fallback check - if we expected static but failed
            raise ValueError(f"Missing configuration for {provider_name} (Client ID)")

        # Generate State and PKCE
        state = secrets.token_urlsafe(32) # Use random string as state
        
        # Use config for redirect_uri
        redirect_uri = config.OAUTH_REDIRECT_URI
        
        extra_params = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "scope": " ".join(oauth_config.scopes),
            "access_type": "offline", # Google specific for refresh token
            "prompt": "consent",      # Google specific
        }
        
        # Add provider-specific extra params (e.g. audience for Atlassian)
        if hasattr(oauth_config, "extra_auth_params") and oauth_config.extra_auth_params:
            extra_params.update(oauth_config.extra_auth_params)

        if oauth_config.pkce:
            verifier, challenge = generate_pkce()
            extra_params.update({
                "code_challenge": challenge,
                "code_challenge_method": "S256"
            })
            # Store verifier
            AUTH_CACHE[state] = {
                "verifier": verifier,
                "provider": provider_name,
                "user_id": str(user_id),
                "redirect_url": redirect_url_frontend,
                "target_app": final_target_app
            }
        else:
             AUTH_CACHE[state] = {
                "provider": provider_name,
                "user_id": str(user_id),
                "redirect_url": redirect_url_frontend,
                "target_app": final_target_app
            }

        # Build URL
        from urllib.parse import urlencode
        return f"{oauth_config.authorize_url}?{urlencode(extra_params)}"

    async def exchange_code(self, code: str, state: str) -> Tuple[str, str, str, Optional[str]]:
        """
        Exchanges code for token.
        Saves token to DB.
        Returns (frontend_url, user_id, provider_name, target_app).
        """
        cache_data = AUTH_CACHE.pop(state, None)
        if not cache_data:
            raise ValueError("Invalid or expired state")
            
        # Dynamic Exchange Delegation
        if cache_data.get("is_dynamic"):
            AUTH_CACHE[state] = cache_data # Put back for dynamic handler
            return await self.exchange_code_dynamic(code, state)

        provider_name = cache_data["provider"]
        user_id = cache_data["user_id"]
        frontend_url = cache_data["redirect_url"]
        target_app = cache_data.get("target_app")
        verifier = cache_data.get("verifier")

        provider = get_oauth_config_by_provider(provider_name)
        client_id = getattr(config, provider.client_id_env)
        client_secret = getattr(config, provider.client_secret_env)

        # Prepare Request
        # Use config for redirect_uri
        redirect_uri = config.OAUTH_REDIRECT_URI
        
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "client_secret": client_secret,
        }
        
        if verifier:
            data["code_verifier"] = verifier

        # Execute Exchange
        async with httpx.AsyncClient() as client:
            resp = await client.post(provider.token_url, data=data, headers={"Accept": "application/json"})
            resp.raise_for_status()
            token_data = resp.json()

        # Save to DB - use target_app as app_id for per-app token storage
        await self._save_token(user_id, provider_name, token_data, app_id=target_app)

        return frontend_url, user_id, provider_name, target_app

    def get_state_data(self, state: str) -> Optional[Dict[str, str]]:
        """
        Retrieve state data (redirect_url, etc.) without exchanging code.
        Useful for error handling in callback.
        """
        return AUTH_CACHE.pop(state, None)

    async def _save_token(self, user_id: str, provider: str, data: Dict[str, Any], app_id: Optional[str] = None):
        """Upsert token in DB using app_id for per-app storage."""
        access_token = data.get("access_token")
        refresh_token = data.get("refresh_token")
        
        # Only track expiry if we have a refresh token to renew it
        # Tokens without refresh capability are treated as persistent
        expires_in = data.get("expires_in")
        expires_at = None
        if refresh_token and expires_in is not None:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
        elif not refresh_token and expires_in is not None:
            logger.info(f"No refresh_token for {provider} - treating as persistent (ignoring expires_in: {expires_in}s)")

        async with AsyncSessionLocal() as session:
            # Check existing by app_id (or provider if app_id not provided for backward compat)
            if app_id:
                stmt = select(OAuthToken).where(
                    OAuthToken.user_id == user_id,
                    OAuthToken.app_id == app_id
                )
            else:
                # Legacy fallback - lookup by provider
                stmt = select(OAuthToken).where(
                    OAuthToken.user_id == user_id,
                    OAuthToken.provider == provider,
                    OAuthToken.app_id == None
                )
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                existing.access_token = access_token
                if refresh_token: # Only update if new one provided
                    existing.refresh_token = refresh_token
                existing.expires_at = expires_at
                existing.raw = data
                existing.updated_at = datetime.now(timezone.utc)
                # Update app_id if it was missing
                if app_id and not existing.app_id:
                    existing.app_id = app_id
            else:
                new_token = OAuthToken(
                    user_id=user_id,
                    app_id=app_id,
                    provider=provider,
                    access_token=access_token,
                    refresh_token=refresh_token,
                    expires_at=expires_at,
                    scope=json.dumps(data.get("scope", "")),
                    raw=data
                )
                session.add(new_token)
            
            await session.commit()
            logger.info(f"Saved OAuth token for user {user_id}, app_id={app_id}, provider={provider}")
            
    async def get_valid_token(self, user_id: str, app_id: str) -> Optional[str]:
        """
        Get a valid access token by app_id. Refresh if expired.
        """
        async with AsyncSessionLocal() as session:
            stmt = select(OAuthToken).where(
                OAuthToken.user_id == user_id,
                OAuthToken.app_id == app_id
            )
            token = (await session.execute(stmt)).scalar_one_or_none()
            
            if not token:
                return None
                
            if token.is_expired:
                logger.info(f"Token for {app_id} is EXPIRED (Now: {datetime.now(timezone.utc)}, Exp: {token.expires_at}). Refreshing...")
                return await self.refresh_token(token, session)
            
            logger.info(f"Token for {app_id} is VALID (Now: {datetime.now(timezone.utc)}, Exp: {token.expires_at}). Using existing.")
            return token.access_token

    async def get_full_credentials(self, user_id: str, app_id: str) -> Optional[Dict[str, Any]]:
        """
        Get full credentials (access + refresh + client details) for file-based auth.
        Used for servers like Gmail that expect a credentials.json file.
        Now looks up by app_id for per-app token storage.
        """
        async with AsyncSessionLocal() as session:
            stmt = select(OAuthToken).where(
                OAuthToken.user_id == user_id,
                OAuthToken.app_id == app_id
            )
            token = (await session.execute(stmt)).scalar_one_or_none()
            
            if not token:
                return None
            
            # Get provider config from the app's oauth_config
            from backend.app.core.mcp.registry import get_app_by_id
            app = get_app_by_id(app_id)
            if not app or not app.oauth_config:
                logger.warning(f"No OAuth config found for app {app_id}")
                return None
                
            client_id = app.oauth_config.client_id
            if not client_id and app.oauth_config.client_id_env:
                client_id = getattr(config, app.oauth_config.client_id_env, None)

            client_secret = app.oauth_config.client_secret
            if not client_secret and app.oauth_config.client_secret_env:
                client_secret = getattr(config, app.oauth_config.client_secret_env, None)
            
            # Check for Dynamic Credentials in token.raw
            if token.raw:
                 # Standardize keys from dynamic exchange
                 if "_client_id" in token.raw:
                     client_id = token.raw["_client_id"]
                 if "_client_secret" in token.raw:
                     client_secret = token.raw["_client_secret"]
            
            # Ensure valid token
            if token.is_expired:
                res = await self.refresh_token(token, session)
                if not res:
                     logger.error(f"Failed to refresh expired token for {app_id}")
                     return None
                
            return {
                "token": token.access_token,
                "refresh_token": token.refresh_token,
                "token_uri": app.oauth_config.token_url,
                "client_id": client_id,
                "client_secret": client_secret,
                "scopes": app.oauth_config.scopes,
                "expiry": token.expires_at.isoformat() if token.expires_at else None
            }

    async def refresh_token(self, token: OAuthToken, session: AsyncSession) -> Optional[str]:
        """Refresh logic."""
        if not token.refresh_token:
            logger.warning(f"No refresh token for {token.provider}")
            return None
            
        # Try to resolve config by app_id first
        provider_config = None
        if hasattr(token, 'app_id') and token.app_id:
            from backend.app.core.mcp.registry import get_app_by_id
            app = get_app_by_id(token.app_id)
            if app and app.oauth_config:
                provider_config = app.oauth_config

        if not provider_config:
            provider_config = get_oauth_config_by_provider(token.provider)
            
        client_id = provider_config.client_id
        if not client_id and provider_config.client_id_env:
            client_id = getattr(config, provider_config.client_id_env, None)
            
        client_secret = provider_config.client_secret
        if not client_secret and provider_config.client_secret_env:
            client_secret = getattr(config, provider_config.client_secret_env, None)
        
        # Check for Dynamic Credentials in token.raw (e.g. for Atlassian/Zoho)
        token_url = provider_config.token_url
        if token.raw:
             if "_client_id" in token.raw:
                 client_id = token.raw["_client_id"]
             if "_client_secret" in token.raw:
                 client_secret = token.raw["_client_secret"]
             if "_token_url" in token.raw:
                 token_url = token.raw["_token_url"]
        
        data = {
            "grant_type": "refresh_token",
            "refresh_token": token.refresh_token,
            "client_id": client_id,
            "redirect_uri": config.OAUTH_REDIRECT_URI,
        }
        
        # Generic handling for audience (e.g. for Atlassian)
        if provider_config.extra_auth_params and "audience" in provider_config.extra_auth_params:
             data["audience"] = provider_config.extra_auth_params["audience"]
        
        # Generically decide whether to include client_secret
        # Public clients (like Atlassian DCR) must NOT send it
        if client_secret and getattr(provider_config, "include_client_secret_on_refresh", True):
            data["client_secret"] = client_secret
        
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(token_url, data=data)
                resp.raise_for_status()
                new_data = resp.json()
                
            token.access_token = new_data["access_token"]
            
            # Update expiry if provided, default to 1 hour for refreshed tokens if missing
            new_expires_in = new_data.get("expires_in")
            if new_expires_in:
                 token.expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(new_expires_in))
            else:
                 # If no expiry returned on refresh, assume 1 hour to force subsequent checks 
                 # or keep as is? Standard says it should be there. Default 3600 is safe.
                 token.expires_at = datetime.now(timezone.utc) + timedelta(seconds=3600)
            if "refresh_token" in new_data:
                token.refresh_token = new_data["refresh_token"]
            
            # Merge new data into existing raw to preserve DCR creds (_client_id etc)
            merged_raw = token.raw.copy() if token.raw else {}
            merged_raw.update(new_data)
            token.raw = merged_raw
            
            await session.commit()
            return token.access_token
            
        except Exception as e:
            logger.error(f"Failed to refresh token: {e}")
            return None

    # -------------------------------------------------------------------------
    # Dynamic OAuth (for Zoho and similar providers with custom URLs)
    # -------------------------------------------------------------------------

    async def discover_oauth_metadata(self, server_url: str) -> Dict[str, Any]:
        """
        Discover OAuth metadata from server's well-known endpoint.
        Tries both OAuth and OIDC discovery endpoints.
        """
        from urllib.parse import urlparse
        
        parsed = urlparse(server_url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Try OAuth metadata discovery first
            well_known_url = f"{base_url}/.well-known/oauth-authorization-server"
            try:
                logger.info(f"Discovering OAuth metadata from: {well_known_url}")
                resp = await client.get(well_known_url)
                resp.raise_for_status()
                metadata = resp.json()
                logger.info(f"OAuth metadata discovered successfully")
                return metadata
            except httpx.HTTPError as e:
                logger.debug(f"OAuth discovery failed at {well_known_url}: {e}")
            
            # Try OIDC discovery
            oidc_url = f"{base_url}/.well-known/openid-configuration"
            try:
                logger.info(f"Trying OIDC discovery at: {oidc_url}")
                resp = await client.get(oidc_url)
                resp.raise_for_status()
                metadata = resp.json()
                logger.info(f"OIDC metadata discovered successfully")
                return metadata
            except httpx.HTTPError as e:
                logger.debug(f"OIDC discovery failed at {oidc_url}: {e}")
        
        raise ValueError(
            f"Failed to discover OAuth metadata from {server_url}. "
            "Server must support /.well-known/oauth-authorization-server or /.well-known/openid-configuration"
        )

    async def _dynamic_client_registration(
        self, 
        registration_endpoint: str, 
        redirect_uri: str,
        scopes: Optional[list] = None
    ) -> Tuple[str, Optional[str]]:
        """
        Perform Dynamic Client Registration (DCR).
        Returns (client_id, client_secret) tuple.
        """
        registration_data = {
            "client_name": "AgentSphere",
            "redirect_uris": [redirect_uri],
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "none",  # Public client
            "application_type": "native"
        }
        
        if scopes:
            registration_data["scope"] = " ".join(scopes)
        
        logger.info(f"Attempting Dynamic Client Registration at: {registration_endpoint}")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                resp = await client.post(
                    registration_endpoint,
                    json=registration_data,
                    headers={"Content-Type": "application/json"}
                )
                resp.raise_for_status()
                data = resp.json()
                
                client_id = data.get("client_id")
                client_secret = data.get("client_secret")
                
                logger.info(f"DCR successful! Client ID: {client_id[:20]}...")
                return client_id, client_secret
                
            except httpx.HTTPError as e:
                logger.error(f"DCR failed: {e}")
                if hasattr(e, 'response') and e.response:
                    logger.error(f"DCR response: {e.response.text}")
                raise ValueError(
                    "Dynamic Client Registration failed. "
                    "Server may not support DCR or requires manual client registration."
                )

    async def start_dynamic_auth(
        self, 
        user_id: str, 
        server_url: str, 
        redirect_url_frontend: str,
        target_app: Optional[str] = None
    ) -> str:
        """
        Start OAuth flow for a server with dynamic metadata discovery.
        Used for providers like Zoho where the URL is user-provided.
        Fallback to Manual Auth if URL contains 'key=' and OAuth discovery fails.
        """
        redirect_uri = config.OAUTH_REDIRECT_URI
        
        # 0. Check for Manual Auth Key in URL
        from urllib.parse import urlparse, parse_qs
        parsed_url = urlparse(server_url)
        query_params = parse_qs(parsed_url.query)
        has_key = "key" in query_params
        
        # 1. Discover OAuth metadata from server
        try:
            metadata = await self.discover_oauth_metadata(server_url)
        except ValueError as e:
            # Fallback: If discovery fails but we have a key, assume Manual Auth
            if has_key:
                logger.info(f"OAuth discovery failed but found 'key' in URL. Falling back to Manual Auth for {server_url}")
                
                # Determine provider name generically
                provider_name = "dynamic_oauth" # Default fallback
                if target_app:
                    from backend.app.core.mcp.registry import get_app_by_id
                    app = get_app_by_id(target_app)
                    if app and app.oauth_config:
                        provider_name = app.oauth_config.provider_name
                elif server_url:
                     from urllib.parse import urlparse
                     provider_name = urlparse(server_url).netloc

                # Generate state for cache key
                state = secrets.token_urlsafe(32)
                
                # Store data for callback bypass
                AUTH_CACHE[state] = {
                    "provider": provider_name,
                    "user_id": str(user_id),
                    "redirect_url": redirect_url_frontend,
                    "server_url": server_url,
                    "target_app": target_app,
                    "is_dynamic": True,
                    "is_bypass": True  # Flag for manual auth bypass
                }
                
                # Must return a URL that redirects to OUR callback with the bypass code
                from urllib.parse import urlencode
                params = {
                    "state": state,
                    "code": "BYPASS_MANUAL_AUTH"
                }
                logger.info("Redirecting to local callback for manual auth bypass")
                return f"{redirect_uri}?{urlencode(params)}"
                
            # If no key, re-raise error
            raise e
        
        authorize_url = metadata.get("authorization_endpoint")
        token_url = metadata.get("token_endpoint")
        registration_endpoint = metadata.get("registration_endpoint")
        scopes_supported = metadata.get("scopes_supported", [])
        
        if not authorize_url or not token_url:
            raise ValueError("OAuth metadata missing required endpoints (authorization_endpoint, token_endpoint)")
        
        # 2. Get or register client credentials
        client_id = None
        client_secret = None
        
        # Check if we have stored DCR credentials for this server
        dcr_cache = await self._load_dcr_credentials(server_url)
        if dcr_cache:
            client_id = dcr_cache.get("client_id")
            client_secret = dcr_cache.get("client_secret")
            logger.info(f"Using cached DCR credentials for {server_url}")
        
        # If no cached credentials, try DCR
        if not client_id and registration_endpoint:
            client_id, client_secret = await self._dynamic_client_registration(
                registration_endpoint, 
                redirect_uri,
                scopes_supported[:5] if scopes_supported else None  # Limit scopes
            )
            # Cache the credentials
            await self._save_dcr_credentials(server_url, client_id, client_secret)
        
        if not client_id:
            raise ValueError(
                "Could not obtain OAuth client credentials. "
                "Server does not support Dynamic Client Registration. "
                "Please register an OAuth app manually and provide client_id."
            )
        
        # 3. Generate PKCE
        verifier, challenge = generate_pkce()
        state = secrets.token_urlsafe(32)
        
        # Determine provider name generically
        provider_name = "dynamic_oauth" # Default fallback
        if target_app:
            from backend.app.core.mcp.registry import get_app_by_id
            app = get_app_by_id(target_app)
            if app and app.oauth_config:
                provider_name = app.oauth_config.provider_name
        elif server_url:
             from urllib.parse import urlparse
             provider_name = urlparse(server_url).netloc

        # 4. Store all necessary data in cache for callback
        AUTH_CACHE[state] = {
            "verifier": verifier,
            "provider": provider_name,
            "user_id": str(user_id),
            "redirect_url": redirect_url_frontend,
            "server_url": server_url,
            "target_app": target_app,
            "token_url": token_url,
            "client_id": client_id,
            "client_secret": client_secret,
            "is_dynamic": True,  # Flag to indicate dynamic OAuth
            "scope": None  # Will be set below after we build scope_str
        }
        
        # 5. Build authorization URL
        params = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256"
        }
        
        # Add scope from App Config if available
        scope_str = ""
        if target_app:
             from backend.app.core.mcp.registry import get_app_by_id
             app_def = get_app_by_id(target_app)
             if app_def and app_def.oauth_config and app_def.oauth_config.scopes:
                 scope_str = " ".join(app_def.oauth_config.scopes)
                 # Also add extra params
                 if app_def.oauth_config.extra_auth_params:
                     params.update(app_def.oauth_config.extra_auth_params)

        if not scope_str and scopes_supported:
            scope_str = " ".join(scopes_supported[:5])
        
        # CRITICAL: Always ensure offline_access is included for refresh token support
        # This is the OAuth 2.0 standard way to request a refresh token
        if scope_str and "offline_access" not in scope_str:
            scope_str = scope_str + " offline_access"
            logger.info(f"Added 'offline_access' scope for refresh token support")
        
        # Store scope in cache for use during token exchange
        AUTH_CACHE[state]["scope"] = scope_str
            
        if scope_str:
            params["scope"] = scope_str
        
        from urllib.parse import urlencode
        auth_url = f"{authorize_url}?{urlencode(params)}"
        
        logger.info(f"Generated dynamic OAuth URL for {server_url}")
        return auth_url

    async def exchange_code_dynamic(self, code: str, state: str) -> Tuple[str, str, str, Optional[str]]:
        """
        Exchange authorization code for tokens (for dynamic OAuth providers).
        Returns (frontend_url, user_id, provider_name, target_app).
        """
        cache_data = AUTH_CACHE.pop(state, None)
        if not cache_data:
            raise ValueError("Invalid or expired state")
        
        if not cache_data.get("is_dynamic"):
            # Not a dynamic provider, use regular exchange
            # Re-add to cache and call regular method
            AUTH_CACHE[state] = cache_data
            return await self.exchange_code(code, state)
        
        user_id = cache_data["user_id"]
        frontend_url = cache_data["redirect_url"]
        server_url = cache_data["server_url"]
        target_app = cache_data.get("target_app")
        
        # Handle BYPASS for manual auth
        if code == "BYPASS_MANUAL_AUTH" and cache_data.get("is_bypass"):
            logger.info(f"Processing manual auth bypass for {server_url}")
            # Create a dummy token structure
            token_data = {
                "access_token": "", # No token needed as key is in URL
                "expires_in": 315360000, # 10 years
                "scope": "all",
                "token_type": "Bearer",
                "_server_url": server_url,
                "_bypass": True
            }
            await self._save_token(user_id, cache_data.get("provider", "dynamic_oauth"), token_data, app_id=target_app)
            return frontend_url, user_id, cache_data.get("provider", "dynamic_oauth"), target_app

        # Dynamic OAuth exchange
        verifier = cache_data.get("verifier")
        token_url = cache_data["token_url"]
        client_id = cache_data["client_id"]
        client_secret = cache_data.get("client_secret")
        
        redirect_uri = config.OAUTH_REDIRECT_URI
        
        # Prepare token request
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
        }
        
        if client_secret:
            data["client_secret"] = client_secret
        if verifier:
            data["code_verifier"] = verifier
        
        # Include scope in token request - some servers require this to return refresh_token
        scope = cache_data.get("scope")
        if scope:
            data["scope"] = scope
        
        logger.info(f"Exchanging code for tokens at: {token_url}")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                token_url, 
                data=data, 
                headers={"Accept": "application/json"}
            )
            resp.raise_for_status()
            token_data = resp.json()
        
        # DEBUG: Log the actual response to see if refresh_token is present
        logger.info(f"Token response keys: {list(token_data.keys())}")
        if "refresh_token" in token_data:
            logger.info(f"✅ Refresh token RECEIVED from {token_url}")
        else:
            logger.warning(f"⚠️ NO refresh_token in response from {token_url}. Keys: {list(token_data.keys())}")
        
        # Store server_url in token metadata for later use
        token_data["_server_url"] = server_url
        token_data["_token_url"] = token_url
        token_data["_client_id"] = client_id
        token_data["_client_secret"] = client_secret
        
        # Save to DB with target_app as app_id for per-app storage
        provider_name = cache_data.get("provider", "dynamic_oauth")
        await self._save_token(user_id, provider_name, token_data, app_id=target_app)
        
        logger.info(f"Dynamic OAuth successful for user {user_id}, app_id={target_app}")
        return frontend_url, user_id, provider_name, target_app

    async def _save_dcr_credentials(self, server_url: str, client_id: str, client_secret: Optional[str]):
        """Store DCR credentials for a server URL."""
        from pathlib import Path
        import hashlib
        
        # Create a hash of the URL for filename
        url_hash = hashlib.md5(server_url.encode()).hexdigest()[:16]
        
        dcr_dir = Path.home() / ".agentsphere" / "dcr"
        dcr_dir.mkdir(parents=True, exist_ok=True)
        
        dcr_file = dcr_dir / f"{url_hash}.json"
        dcr_data = {
            "server_url": server_url,
            "client_id": client_id,
            "client_secret": client_secret
        }
        
        dcr_file.write_text(json.dumps(dcr_data))
        logger.debug(f"Saved DCR credentials for {server_url}")

    async def _load_dcr_credentials(self, server_url: str) -> Optional[Dict[str, Any]]:
        """Load DCR credentials for a server URL if they exist."""
        from pathlib import Path
        import hashlib
        
        url_hash = hashlib.md5(server_url.encode()).hexdigest()[:16]
        dcr_file = Path.home() / ".agentsphere" / "dcr" / f"{url_hash}.json"
        
        if dcr_file.exists():
            try:
                data = json.loads(dcr_file.read_text())
                if data.get("server_url") == server_url:
                    return data
            except (json.JSONDecodeError, IOError):
                pass
        
        return None

    async def get_token_metadata(self, user_id: str, app_id: str) -> Optional[Dict[str, Any]]:
        """Get raw token metadata (including custom fields like _server_url) by app_id."""
        async with AsyncSessionLocal() as session:
            stmt = select(OAuthToken).where(
                OAuthToken.user_id == user_id,
                OAuthToken.app_id == app_id
            )
            token = (await session.execute(stmt)).scalar_one_or_none()
            
            if token:
                return token.raw
            return None

oauth_service = OAuthService()
