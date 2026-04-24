import base64
from cryptography.fernet import Fernet
from app.core.config import settings


def get_fernet() -> Fernet:
    """
    Get a Fernet instance using the configured encryption key.
    Settings.ENCRYPTION_KEY should be a valid base64-encoded Fernet key (44 chars).
    """
    key = settings.ENCRYPTION_KEY
    # If it's bytes (from Pydantic env variable), convert to string for Fernet
    if isinstance(key, bytes):
        key = key.decode('utf-8')
    return Fernet(key)


def encrypt_data(data: str) -> str:
    """
    Encrypt a string using symmetric encryption.
    """
    if not data:
        return data
    f = get_fernet()
    return f.encrypt(data.encode()).decode()


def decrypt_data(encrypted_data: str) -> str:
    """
    Decrypt an encrypted string.
    """
    if not encrypted_data:
        return encrypted_data
    f = get_fernet()
    return f.decrypt(encrypted_data.encode()).decode()
