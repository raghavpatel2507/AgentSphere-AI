"""
Token Manager for MCP OAuth Authentication.

Handles per-user token storage in database for multi-user isolation.
All tokens are stored exclusively in the oauth_tokens table.
"""

import os
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional
from datetime import datetime, timezone, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db import async_engine
from backend.app.core.state.models import OAuthToken
from backend.app.core.auth.security import encrypt_config, decrypt_config

logger = logging.getLogger(__name__)


class TokenManager:
    """Manages OAuth tokens for MCP servers with per-user database storage."""
    
    def __init__(self, user_id: Any):
        if isinstance(user_id, str):
            try:
                self.user_id = UUID(user_id)
            except (ValueError, TypeError):
                # Fallback if not a valid UUID string (though it should be)
                self.user_id = user_id
        else:
            self.user_id = user_id
    
    async def get_token(self, service: str) -> Optional[Dict[str, Any]]:
        """
        Get OAuth token for a service.
        
        Returns token from database, refreshing if expired.
        """
        logger.info(f"🔍 TokenManager.get_token: user_id={self.user_id}, service={service}")
        
        async with AsyncSession(async_engine) as session:
            stmt = select(OAuthToken).where(
                OAuthToken.user_id == self.user_id,
                OAuthToken.service == service
            )
            result = await session.execute(stmt)
            token_record = result.scalar_one_or_none()
            
            if not token_record:
                logger.warning(f"❌ No token found for service={service}, user_id={self.user_id}")
                return None
            
            # CRITICAL: Verify token belongs to requesting user (defensive check)
            if token_record.user_id != self.user_id:
                logger.error(f"🚨 SECURITY VIOLATION: Token user_id mismatch! "
                           f"Requested by user_id={self.user_id}, but token belongs to user_id={token_record.user_id}, "
                           f"service={service}")
                raise ValueError(f"Token user_id mismatch for service {service}")
            
            logger.info(f"✅ Found token for user_id={self.user_id}, service={service}, "
                       f"expires_at={token_record.expires_at}, scopes={token_record.scopes}")
            
            # Check if token is expired
            if token_record.is_expired and token_record.refresh_token:
                logger.info(f"⚠️  Token expired for {service}, attempting refresh")
                # Token refresh will be handled by mcp-use library
                # We just return the refresh token
                pass
            
            # Decrypt and return token data
            token_data = {
                "access_token": token_record.access_token,
                "refresh_token": token_record.refresh_token,
                "token_uri": token_record.token_uri,
                "scopes": token_record.scopes,
                "expires_at": token_record.expires_at.isoformat() if token_record.expires_at else None,
            }
            
            return token_data
    
    async def store_token(
        self,
        service: str,
        access_token: str,
        refresh_token: Optional[str] = None,
        token_uri: Optional[str] = None,
        scopes: Optional[list] = None,
        expires_in: Optional[int] = None
    ) -> None:
        """
        Store OAuth token in database.
        
        Args:
            service: Service name (e.g., 'github', 'linear')
            access_token: OAuth access token
            refresh_token: OAuth refresh token (optional)
            token_uri: Token endpoint URI for refresh
            scopes: List of OAuth scopes
            expires_in: Token expiration time in seconds
        """
        try:
            logger.info(f"💾 TokenManager.store_token: user_id={self.user_id}, service={service}, "
                       f"has_refresh_token={refresh_token is not None}, scopes={scopes}")
            
            expires_at = None
            if expires_in:
                expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
                logger.info(f"   Token expires at: {expires_at}")
            
            async with AsyncSession(async_engine) as session:
                logger.info(f"   Database session created")
                
                # Check if token already exists
                stmt = select(OAuthToken).where(
                    OAuthToken.user_id == self.user_id,
                    OAuthToken.service == service
                )
                result = await session.execute(stmt)
                token_record = result.scalar_one_or_none()
                
                if token_record:
                    logger.info(f"   Updating existing token record")
                    # Update existing token
                    token_record.access_token = access_token
                    token_record.refresh_token = refresh_token
                    token_record.token_uri = token_uri
                    token_record.scopes = scopes or []
                    token_record.expires_at = expires_at
                    token_record.updated_at = datetime.now(timezone.utc)
                else:
                    logger.info(f"   Creating new token record")
                    # Create new token
                    token_record = OAuthToken(
                        user_id=self.user_id,
                        service=service,
                        access_token=access_token,
                        refresh_token=refresh_token,
                        token_uri=token_uri,
                        scopes=scopes or [],
                        expires_at=expires_at
                    )
                    session.add(token_record)
                
                logger.info(f"   Committing to database...")
                await session.commit()
                logger.info(f"✅ Token stored successfully in database for service={service}")
                
        except Exception as e:
            logger.error(f"❌ FAILED to store token for service={service}: {e}")
            logger.error(f"   Error type: {type(e).__name__}")
            import traceback
            logger.error(f"   Traceback: {traceback.format_exc()}")
            raise
    
    async def delete_token(self, service: str) -> bool:
        """Delete token from database."""
        async with AsyncSession(async_engine) as session:
            stmt = select(OAuthToken).where(
                OAuthToken.user_id == self.user_id,
                OAuthToken.service == service
            )
            result = await session.execute(stmt)
            token_record = result.scalar_one_or_none()
            
            if token_record:
                await session.delete(token_record)
                await session.commit()
                logger.info(f"Deleted token for service {service}, user {self.user_id}")
                return True
        
        return False
    
    async def refresh_token(self, service: str) -> Optional[Dict[str, Any]]:
        """
        Refresh an expired OAuth token.
        
        Note: Actual refresh logic is handled by mcp-use library.
        This method retrieves the refresh token from database.
        """
        token_data = await self.get_token(service)
        if not token_data or not token_data.get("refresh_token"):
            logger.warning(f"No refresh token available for {service}")
            return None
        
        return token_data
    
    async def cleanup_user_tokens(self) -> None:
        """Delete all tokens for this user from database."""
        async with AsyncSession(async_engine) as session:
            stmt = select(OAuthToken).where(OAuthToken.user_id == self.user_id)
            result = await session.execute(stmt)
            tokens = result.scalars().all()
            
            for token in tokens:
                await session.delete(token)
            
            await session.commit()
            logger.info(f"Cleaned up all tokens for user {self.user_id} from database")
