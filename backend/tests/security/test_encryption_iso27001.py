from cryptography.fernet import Fernet
import pytest
from app.utils.encryption import encrypt_data, decrypt_data
from app.core.config import settings

def test_sensitive_data_encryption():
    sensitive_text = "Highly Confidential Meeting Minutes"
    
    # Verschlüsseln
    encrypted = encrypt_data(sensitive_text)
    assert encrypted != sensitive_text
    
    # Entschlüsseln
    decrypted = decrypt_data(encrypted)
    assert decrypted == sensitive_text

def test_encryption_key_rotation_readiness():
    # Testet ob das System mit verschiedenen Keys umgehen kann (Vorbereitung Key Rotation)
    old_key = b"12345678901234567890123456789012"
    new_key = b"09876543210987654321098765432109"
    
    data = "Rotating keys is important for ISO 27001"
    
    with pytest.MonkeyPatch.context() as m:
        m.setattr(settings, "ENCRYPTION_KEY", old_key)
        encrypted_old = encrypt_data(data)
        
        m.setattr(settings, "ENCRYPTION_KEY", new_key)
        # Sollte fehlschlagen beim Entschlüsseln mit falschem Key
        with pytest.raises(Exception):
            decrypt_data(encrypted_old)