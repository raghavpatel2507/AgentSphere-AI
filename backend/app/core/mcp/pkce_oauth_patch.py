"""
PKCE OAuth Patch for mcp-use library.

This module patches the mcp-use OAuth class to add PKCE support.
Since mcp-use doesn't natively support PKCE, we monkey-patch the
AsyncOAuth2Client to inject PKCE parameters.
"""

import logging
from typing import Any
from authlib.integrations.httpx_client import AsyncOAuth2Client

from backend.app.api.v1.oauth.pkce import generate_pkce

logger = logging.getLogger(__name__)

# Store original AsyncOAuth2Client methods
_original_create_authorization_url = AsyncOAuth2Client.create_authorization_url
_original_fetch_token = AsyncOAuth2Client.fetch_token

# Global PKCE storage (will be set when needed)
_pkce_params = {}

# Track if patch has been applied
_patch_applied = False


def enable_pkce_for_server(server_name: str):
    """
    Enable PKCE for a specific server by generating and storing PKCE parameters.
    """
    code_verifier, code_challenge = generate_pkce()
    _pkce_params[server_name] = {
        'code_verifier': code_verifier,
        'code_challenge': code_challenge
    }
    logger.info(f"🔐 Generated PKCE parameters for {server_name}")
    return code_verifier, code_challenge


def create_authorization_url_with_pkce(self, url, **kwargs):
    """
    Patched create_authorization_url that adds PKCE parameters.
    """
    # Check if we have PKCE params for any server (we'll add them if available)
    if _pkce_params:
        # Get the first available PKCE params (there should only be one active at a time)
        for server_name, params in _pkce_params.items():
            kwargs['code_challenge'] = params['code_challenge']
            kwargs['code_challenge_method'] = 'S256'
            logger.info(f"🔐 Injected PKCE challenge into authorization URL for {server_name}")
            break
    
    return _original_create_authorization_url(self, url, **kwargs)


async def fetch_token_with_pkce(self, url, **kwargs):
    """
    Patched fetch_token that adds code_verifier.
    """
    # Check if we have PKCE params
    if _pkce_params:
        # Get the first available PKCE params
        for server_name, params in list(_pkce_params.items()):
            kwargs['code_verifier'] = params['code_verifier']
            logger.info(f"🔐 Injected PKCE verifier into token exchange for {server_name}")
            # Clear the PKCE params after use
            _pkce_params.pop(server_name, None)
            break
    
    return await _original_fetch_token(self, url, **kwargs)


def apply_pkce_patch():
    """
    Apply the PKCE patch to AsyncOAuth2Client.
    This is idempotent - safe to call multiple times.
    """
    global _patch_applied
    
    if _patch_applied:
        logger.debug("PKCE patch already applied, skipping")
        return
    
    AsyncOAuth2Client.create_authorization_url = create_authorization_url_with_pkce
    AsyncOAuth2Client.fetch_token = fetch_token_with_pkce
    _patch_applied = True
    logger.info("✅ PKCE patch applied to AsyncOAuth2Client")


def remove_pkce_patch():
    """
    Remove the PKCE patch and restore original methods.
    """
    global _patch_applied
    
    if not _patch_applied:
        logger.debug("PKCE patch not applied, nothing to remove")
        return
    
    AsyncOAuth2Client.create_authorization_url = _original_create_authorization_url
    AsyncOAuth2Client.fetch_token = _original_fetch_token
    _pkce_params.clear()
    _patch_applied = False
    logger.info("🔄 PKCE patch removed from AsyncOAuth2Client")

