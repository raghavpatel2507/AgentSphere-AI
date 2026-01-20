import secrets
import hashlib
import base64
from typing import Tuple

def generate_pkce(length: int = 64) -> Tuple[str, str]:
    """
    Generate PKCE code verifier and challenge.
    Returns: (verifier, challenge)
    """
    if length < 43 or length > 128:
        raise ValueError("PKCE verifier length must be between 43 and 128 characters")
        
    verifier = secrets.token_urlsafe(length)
    
    # Calculate SHA256 hash
    digest = hashlib.sha256(verifier.encode('ascii')).digest()
    
    # Base64 url encode without padding
    challenge = base64.urlsafe_b64encode(digest).rstrip(b'=').decode('ascii')
    
    return verifier, challenge