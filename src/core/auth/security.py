
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
def _initialize_cipher():
    key = os.getenv("ENCRYPTION_KEY", "").strip()
    
    # Clean quotes
    if (key.startswith("'") and key.endswith("'")) or (key.startswith('"') and key.endswith('"')):
        key = key[1:-1].strip()
    
    # Try to initialize
    try:
        if not key: raise ValueError("Empty key")
        return Fernet(key.encode()), key
    except Exception:
        new_key = Fernet.generate_key().decode()
        logger.warning(f"⚠️ ENCRYPTION_KEY is invalid or missing. Generating a new one. DATA PROTECTED BY THE OLD KEY WILL BE UNREADABLE.")
        
        # Self-healing: try to update .env
        try:
            env_path = os.path.join(os.getcwd(), ".env")
            if os.path.exists(env_path):
                with open(env_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                
                with open(env_path, "w", encoding="utf-8") as f:
                    found = False
                    for line in lines:
                        if line.startswith("ENCRYPTION_KEY="):
                            f.write(f"ENCRYPTION_KEY={new_key}\n")
                            found = True
                        else:
                            f.write(line)
                    if not found:
                        f.write(f"\nENCRYPTION_KEY={new_key}\n")
                logger.info("✅ Automatically updated .env with a valid ENCRYPTION_KEY.")
        except Exception as e:
            logger.error(f"❌ Failed to auto-update .env: {e}")
            
        return Fernet(new_key.encode()), new_key

cipher_suite, _current_key = _initialize_cipher()

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

def decrypt_config(config: dict) -> dict:
    """Decrypt sensitive env vars in an MCP server configuration."""
    import copy
    c = copy.deepcopy(config)
    if "env" in c and isinstance(c["env"], dict):
        for k, v in c["env"].items():
            if any(s in k.upper() for s in ["KEY", "TOKEN", "SECRET", "PASSWORD"]):
                if isinstance(v, str) and not v.startswith("${"):
                    decrypted = decrypt_value(v)
                    if decrypted == "[DECRYPTION_FAILED]":
                        logger.error(f"Decryption failed for key: {k}")
                    else:
                        c["env"][k] = decrypted
    return c
