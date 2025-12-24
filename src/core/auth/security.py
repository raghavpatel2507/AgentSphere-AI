
import os
from passlib.context import CryptContext
from cryptography.fernet import Fernet
import base64
import logging
from dotenv import load_dotenv

# Load .env file
load_dotenv()

logger = logging.getLogger(__name__)

# Password Hashing Context (Argon2 for robustness)
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Generate a hash for a password."""
    return pwd_context.hash(password)

# Encryption Handling
# We expect an ENCRYPTION_KEY in env, or we generate a temporary one (warning: data loss on restart if temporary)
_ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", "").strip().strip("'").strip('"')

if not _ENCRYPTION_KEY:
    logger.warning("⚠️ ENCRYPTION_KEY not found in environment. Generating a temporary key. ENCRYPTED DATA WILL BE LOST ON RESTART.")
    _ENCRYPTION_KEY = Fernet.generate_key().decode()
    # In production, you would fix this. For dev, we'll proceed.

# Final cleanup to ensure it's a valid Fernet key length
try:
    cipher_suite = Fernet(_ENCRYPTION_KEY.encode() if isinstance(_ENCRYPTION_KEY, str) else _ENCRYPTION_KEY)
except Exception as e:
    logger.error(f"❌ Critical Error: Invalid ENCRYPTION_KEY format: {e}")
    # Fallback to a temporary key to prevent crash if .env is broken
    _ENCRYPTION_KEY = Fernet.generate_key()
    cipher_suite = Fernet(_ENCRYPTION_KEY)

def encrypt_value(value: str) -> str:
    """Encrypt a string value."""
    if not value: return value
    return cipher_suite.encrypt(value.encode()).decode()

def decrypt_value(encrypted_value: str) -> str:
    """Decrypt a string value."""
    if not encrypted_value: return encrypted_value
    try:
        return cipher_suite.decrypt(encrypted_value.encode()).decode()
    except Exception as e:
        logger.error(f"Decryption failed: {e}")
        return "[DECRYPTION_FAILED]"
