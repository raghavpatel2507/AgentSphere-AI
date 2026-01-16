import logging
import json
import secrets
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.oauth.registry import get_provider
from backend.app.core.oauth.pkce import generate_pkce
from backend.app.core.state.models import OAuthToken, User
from backend.app.config import config
from backend.app.db import AsyncSessionLocal

logger = logging.getLogger(__name__)

# Simple in-memory cache for PKCE/State (Redis is better for production)
# Structure: { "state_string": { "verifier": "...", "provider": "...", "user_id": "...", "redirect_url": "..." } }
AUTH_CACHE: Dict[str, Dict[str, str]] = {}

class OAuthService:

    async def start_auth(self, provider_name: str, user_id: str, redirect_url_frontend: str) -> str:
        """
        Generates the authorization URL for the given provider.
        Stores state/verifier in cache.
        """
        provider = get_provider(provider_name)
        if not provider:
            raise ValueError(f"Provider {provider_name} not configured")

        client_id = getattr(config, provider.client_id_env, None)
        if not client_id:
            raise ValueError(f"Missing configuration for {provider_name} (Client ID)")

        # Generate State and PKCE
        state = secrets.token_urlsafe(32) # Use random string as state
        extra_params = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": f"http://localhost:8000/api/v1/oauth/callback", # TODO: Make dynamic/env based // hardocded as per user req
            "state": state,
            "scope": " ".join(provider.scopes),
            "access_type": "offline", # Google specific for refresh token
            "prompt": "consent",      # Google specific
        }

        if provider.pkce:
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
                "redirect_url": redirect_url_frontend
            }
        else:
             AUTH_CACHE[state] = {
                "provider": provider_name,
                "user_id": str(user_id),
                "redirect_url": redirect_url_frontend
            }

        # Build URL
        from urllib.parse import urlencode
        return f"{provider.authorize_url}?{urlencode(extra_params)}"

    async def exchange_code(self, code: str, state: str) -> Tuple[str, str, str]:
        """
        Exchanges code for token.
        Saves token to DB.
        Returns (frontend_url, user_id, provider_name).
        """
        cache_data = AUTH_CACHE.pop(state, None)
        if not cache_data:
            raise ValueError("Invalid or expired state")

        provider_name = cache_data["provider"]
        user_id = cache_data["user_id"]
        frontend_url = cache_data["redirect_url"]
        verifier = cache_data.get("verifier")

        provider = get_provider(provider_name)
        client_id = getattr(config, provider.client_id_env)
        client_secret = getattr(config, provider.client_secret_env)

        # Prepare Request
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": "http://localhost:8000/api/v1/oauth/callback",
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

        # Save to DB
        await self._save_token(user_id, provider_name, token_data)

        return frontend_url, user_id, provider_name

    def get_state_data(self, state: str) -> Optional[Dict[str, str]]:
        """
        Retrieve state data (redirect_url, etc.) without exchanging code.
        Useful for error handling in callback.
        """
        return AUTH_CACHE.pop(state, None)

    async def _save_token(self, user_id: str, provider: str, data: Dict[str, Any]):
        """Upsert token in DB."""
        access_token = data.get("access_token")
        refresh_token = data.get("refresh_token")
        expires_in = data.get("expires_in", 3600)
        
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

        async with AsyncSessionLocal() as session:
            # Check existing
            stmt = select(OAuthToken).where(
                OAuthToken.user_id == user_id,
                OAuthToken.provider == provider
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
            else:
                new_token = OAuthToken(
                    user_id=user_id,
                    provider=provider,
                    access_token=access_token,
                    refresh_token=refresh_token,
                    expires_at=expires_at,
                    scope=json.dumps(data.get("scope", "")),
                    raw=data
                )
                session.add(new_token)
            
            await session.commit()
            
    async def get_valid_token(self, user_id: str, provider_name: str) -> Optional[str]:
        """
        Get a valid access token. Refresh if expired.
        """
        async with AsyncSessionLocal() as session:
            stmt = select(OAuthToken).where(
                OAuthToken.user_id == user_id,
                OAuthToken.provider == provider_name
            )
            token = (await session.execute(stmt)).scalar_one_or_none()
            
            if not token:
                return None
                
            if token.is_expired:
                logger.info(f"Token for {provider_name} expired. Refreshing...")
                return await self.refresh_token(token, session)
                
            return token.access_token

    async def get_full_credentials(self, user_id: str, provider_name: str) -> Optional[Dict[str, Any]]:
        """
        Get full credentials (access + refresh + client details) for file-based auth.
        Used for servers like Gmail that expect a credentials.json file.
        """
        async with AsyncSessionLocal() as session:
            stmt = select(OAuthToken).where(
                OAuthToken.user_id == user_id,
                OAuthToken.provider == provider_name
            )
            token = (await session.execute(stmt)).scalar_one_or_none()
            
            if not token:
                return None
                
            provider = get_provider(provider_name)
            client_id = getattr(config, provider.client_id_env)
            client_secret = getattr(config, provider.client_secret_env)
            
            # Ensure valid token
            if token.is_expired:
                await self.refresh_token(token, session)
                
            return {
                "token": token.access_token,
                "refresh_token": token.refresh_token,
                "token_uri": provider.token_url,
                "client_id": client_id,
                "client_secret": client_secret,
                "scopes": provider.scopes,
                "expiry": token.expires_at.isoformat() if token.expires_at else None
            }

    async def refresh_token(self, token: OAuthToken, session: AsyncSession) -> Optional[str]:
        """Refresh logic."""
        if not token.refresh_token:
            logger.warning(f"No refresh token for {token.provider}")
            return None
            
        provider = get_provider(token.provider)
        client_id = getattr(config, provider.client_id_env)
        client_secret = getattr(config, provider.client_secret_env)
        
        data = {
            "grant_type": "refresh_token",
            "refresh_token": token.refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
        }
        
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(provider.token_url, data=data)
                resp.raise_for_status()
                new_data = resp.json()
                
            token.access_token = new_data["access_token"]
            token.expires_at = datetime.now(timezone.utc) + timedelta(seconds=new_data.get("expires_in", 3600))
            if "refresh_token" in new_data:
                token.refresh_token = new_data["refresh_token"]
            
            token.raw = new_data
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
        redirect_url_frontend: str
    ) -> str:
        """
        Start OAuth flow for a server with dynamic metadata discovery.
        Used for providers like Zoho where the URL is user-provided.
        Fallback to Manual Auth if URL contains 'key=' and OAuth discovery fails.
        """
        redirect_uri = "http://localhost:8000/api/v1/oauth/callback"
        
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
                
                # Generate a bypass state
                state = secrets.token_urlsafe(32)
                
                # Store data for callback bypass
                AUTH_CACHE[state] = {
                    "provider": "zoho",
                    "user_id": str(user_id),
                    "redirect_url": redirect_url_frontend,
                    "server_url": server_url,
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
        
        # 4. Store all necessary data in cache for callback
        AUTH_CACHE[state] = {
            "verifier": verifier,
            "provider": "zoho",  # Use "zoho" as provider name for dynamic providers
            "user_id": str(user_id),
            "redirect_url": redirect_url_frontend,
            "server_url": server_url,
            "token_url": token_url,
            "client_id": client_id,
            "client_secret": client_secret,
            "is_dynamic": True  # Flag to indicate dynamic OAuth
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
        
        # Add scope if available
        if scopes_supported:
            params["scope"] = " ".join(scopes_supported[:5])
        
        from urllib.parse import urlencode
        auth_url = f"{authorize_url}?{urlencode(params)}"
        
        logger.info(f"Generated dynamic OAuth URL for {server_url}")
        return auth_url

    async def exchange_code_dynamic(self, code: str, state: str) -> Tuple[str, str, str]:
        """
        Exchange authorization code for tokens (for dynamic OAuth providers).
        Returns (frontend_url, user_id, provider_name).
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
            await self._save_token(user_id, "zoho", token_data)
            return frontend_url, user_id, "zoho"

        # Dynamic OAuth exchange
        verifier = cache_data.get("verifier")
        token_url = cache_data["token_url"]
        client_id = cache_data["client_id"]
        client_secret = cache_data.get("client_secret")
        
        redirect_uri = "http://localhost:8000/api/v1/oauth/callback"
        
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
        
        logger.info(f"Exchanging code for tokens at: {token_url}")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                token_url, 
                data=data, 
                headers={"Accept": "application/json"}
            )
            resp.raise_for_status()
            token_data = resp.json()
        
        # Store server_url in token metadata for later use
        token_data["_server_url"] = server_url
        token_data["_token_url"] = token_url
        token_data["_client_id"] = client_id
        token_data["_client_secret"] = client_secret
        
        # Save to DB under "zoho" provider
        await self._save_token(user_id, "zoho", token_data)
        
        logger.info(f"Dynamic OAuth successful for user {user_id}")
        return frontend_url, user_id, "zoho"

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

    async def get_token_metadata(self, user_id: str, provider_name: str) -> Optional[Dict[str, Any]]:
        """Get raw token metadata (including custom fields like _server_url)."""
        async with AsyncSessionLocal() as session:
            stmt = select(OAuthToken).where(
                OAuthToken.user_id == user_id,
                OAuthToken.provider == provider_name
            )
            token = (await session.execute(stmt)).scalar_one_or_none()
            
            if token:
                return token.raw
            return None

oauth_service = OAuthService()
