"""
Security utilities for password hashing and encryption.
Migrated and enhanced from src/core/auth/security.py
"""

import os
import logging
import json
from passlib.context import CryptContext
from cryptography.fernet import Fernet
from functools import lru_cache

from typing import Any, Dict
from backend.app.config import config

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
    key = config.ENCRYPTION_KEY.strip()
    
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



def encrypt_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Encrypt the entire configuration object.
    
    1. Dump config to JSON string.
    2. Encrypt the string using Fernet.
    3. Return wrapper dict: {"encrypted": <encrypted_str>}
    """

    if not config:
        return {}
        
    try:
        # Convert to JSON string
        json_str = json.dumps(config)
        
        # Encrypt
        cipher = _get_cipher()
        encrypted_bytes = cipher.encrypt(json_str.encode())
        encrypted_str = encrypted_bytes.decode()
        
        return {"encrypted": encrypted_str}
        
    except Exception as e:
        logger.error(f"Failed to encrypt config: {e}")
        raise ValueError("Configuration encryption failed")


def decrypt_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Decrypt the configuration object.
    
    1. Check if it matches {"encrypted": "..."} schema.
    2. Decrypt the string.
    3. Parse back to JSON dict.
    4. Fallback: If not matching schema, assume it's legacy or already decrypted and return as-is.
    """
    if not config:
        return {}
        
    # Check for new encryption schema
    if isinstance(config, dict) and "encrypted" in config and len(config) == 1:
        try:
            encrypted_str = config["encrypted"]
            cipher = _get_cipher()
            decrypted_bytes = cipher.decrypt(encrypted_str.encode())
            decrypted_str = decrypted_bytes.decode()
            return json.loads(decrypted_str)
        except Exception as e:
            logger.error(f"Failed to decrypt config: {e}")
            # Identify if this is a critical failure or corrupt data
            return {}
            
    # Fallback/Legacy: Return as-is (assuming it's plain text or handled elsewhere)
    # The old logic handled field-level encryption, but going forward we assume migration.
    return config

# Export explicitly
__all__ = ["encrypt_config", "decrypt_config", "get_password_hash", "verify_password", "encrypt_value", "decrypt_value"]

