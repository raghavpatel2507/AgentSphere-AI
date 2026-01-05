"""
JWT Token handling for authentication.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from uuid import UUID

from backend.app.config import config


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a new JWT access token.
    
    Args:
        data: Payload data to encode in the token
        expires_delta: Optional custom expiration time
        
    Returns:
        Encoded JWT string
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=config.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "type": "access"})
    
    encoded_jwt = jwt.encode(
        to_encode, 
        config.JWT_SECRET_KEY, 
        algorithm=config.JWT_ALGORITHM
    )
    return encoded_jwt


def create_refresh_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a new JWT refresh token.
    
    Args:
        data: Payload data to encode in the token
        expires_delta: Optional custom expiration time
        
    Returns:
        Encoded JWT string
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=config.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    
    to_encode.update({"exp": expire, "type": "refresh"})
    
    encoded_jwt = jwt.encode(
        to_encode, 
        config.JWT_SECRET_KEY, 
        algorithm=config.JWT_ALGORITHM
    )
    return encoded_jwt


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode and verify a JWT token.
    
    Args:
        token: JWT string to decode
        
    Returns:
        Decoded payload if valid, None otherwise
    """
    try:
        payload = jwt.decode(
            token, 
            config.JWT_SECRET_KEY, 
            algorithms=[config.JWT_ALGORITHM]
        )
        return payload
    except JWTError:
        return None


def get_user_id_from_token(token: str) -> Optional[UUID]:
    """
    Extract user_id from a JWT token.
    
    Args:
        token: JWT string
        
    Returns:
        UUID of the user if valid, None otherwise
    """
    payload = decode_token(token)
    if payload is None:
        return None
    
    user_id_str = payload.get("sub")
    if user_id_str is None:
        return None
    
    try:
        return UUID(user_id_str)
    except ValueError:
        return None
