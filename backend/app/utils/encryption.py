import base64
from cryptography.fernet import Fernet
from app.core.config import settings


def get_fernet() -> Fernet:
    """
    Get a Fernet instance using the configured encryption key.
    The key must be a 32-byte key, which we then base64-encode.
    """
    # Fernet requires a base64 encoded 32-byte key.
    # We take our 32 bytes from settings and encode them.
    key = base64.urlsafe_b64encode(settings.ENCRYPTION_KEY)
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
