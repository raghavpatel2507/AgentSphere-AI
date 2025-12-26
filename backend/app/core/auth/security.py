"""
Security utilities for password hashing and encryption.
Migrated and enhanced from src/core/auth/security.py
"""

import os
import logging
from passlib.context import CryptContext
from cryptography.fernet import Fernet
from functools import lru_cache

from backend.app.config import settings

logger = logging.getLogger(__name__)

# Password Hashing Context (Argon2 for robustness)
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Generate a hash for a password."""
    return pwd_context.hash(password)


@lru_cache()
def _get_cipher() -> Fernet:
    """
    Get or create the Fernet cipher for encryption.
    Cached to avoid reinitializing on every call.
    """
    key = settings.ENCRYPTION_KEY.strip()
    
    # Clean quotes if present
    if (key.startswith("'") and key.endswith("'")) or (key.startswith('"') and key.endswith('"')):
        key = key[1:-1].strip()
    
    if not key:
        logger.warning("⚠️ ENCRYPTION_KEY not set. Generating temporary key - data won't persist across restarts!")
        key = Fernet.generate_key().decode()
    
    try:
        return Fernet(key.encode())
    except Exception:
        logger.warning("⚠️ Invalid ENCRYPTION_KEY. Generating temporary key - data won't persist across restarts!")
        return Fernet(Fernet.generate_key())


def encrypt_value(value: str) -> str:
    """Encrypt a string value."""
    if not value:
        return value
    cipher = _get_cipher()
    return cipher.encrypt(value.encode()).decode()


def decrypt_value(encrypted_value: str) -> str:
    """Decrypt a string value."""
    if not encrypted_value:
        return encrypted_value
    try:
        cipher = _get_cipher()
        return cipher.decrypt(encrypted_value.encode()).decode()
    except Exception as e:
        logger.error(f"Decryption failed: {e}")
        return "[DECRYPTION_FAILED]"
