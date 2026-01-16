import asyncio
import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from backend.app.core.state.models import OAuthToken
from backend.app.db import AsyncSessionLocal
from backend.app.core.oauth.service import oauth_service

logger = logging.getLogger(__name__)

async def refresh_tokens_task():
    """
    Background task to refresh tokens that are close to expiration.
    Run this periodically (e.g., every 10 minutes).
    """
    logger.info("Starting token refresh task...")
    
    # Threshold: refresh if expires in less than 5 minutes
    threshold = datetime.now(timezone.utc) + timedelta(minutes=5)
    
    async with AsyncSessionLocal() as session:
        # Get tokens expiring soon
        stmt = select(OAuthToken).where(
            OAuthToken.expires_at <= threshold,
            OAuthToken.refresh_token.isnot(None) 
        )
        result = await session.execute(stmt)
        expiring_tokens = result.scalars().all()
        
        logger.info(f"Found {len(expiring_tokens)} tokens to refresh")
        
        for token in expiring_tokens:
            try:
                logger.info(f"Refreshing token for user {token.user_id} provider {token.provider}")
                await oauth_service.refresh_token(token, session)
            except Exception as e:
                logger.error(f"Failed to refresh token {token.id}: {e}")
                
    logger.info("Token refresh task completed")

# Helper to run in main loop if needed
async def start_refresh_loop_forever():
    while True:
        try:
            await refresh_tokens_task()
        except Exception as e:
            logger.error(f"Error in refresh loop: {e}")
        await asyncio.sleep(600) # 10 minutes
