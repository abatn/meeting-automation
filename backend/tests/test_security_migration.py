"""
Unit tests for hybrid password verification (bcrypt + passlib migration).

Tests the migration path from passlib/pbkdf2_sha256 to bcrypt.
Ensures backward compatibility with existing password hashes.
"""
import pytest
from app.core.security import get_password_hash, verify_password


class TestPasswordHashingMigration:
    """Test suite for hybrid password verification."""

    def test_bcrypt_hash_creation(self):
        """Test that new passwords are hashed with bcrypt."""
        password = "SecurePassword123!"
        hashed = get_password_hash(password)

        # Bcrypt hashes start with $2b$, $2a$, or $2y$
        assert hashed.startswith('$2b$') or hashed.startswith('$2a$') or hashed.startswith('$2y$'), \
            f"Expected bcrypt hash format, got: {hashed[:10]}..."

        # Verify it works
        assert verify_password(password, hashed) is True

    def test_bcrypt_hash_verification(self):
        """Test that bcrypt hashes are verified correctly."""
        password = "MyPassword@456"
        hashed = get_password_hash(password)

        # Correct password should verify
        assert verify_password(password, hashed) is True

        # Wrong password should fail
        assert verify_password("WrongPassword", hashed) is False

    def test_passlib_hash_verification(self):
        """Test that legacy passlib/pbkdf2_sha256 hashes still work."""
        # Simulate a passlib hash (format: pbkdf2_sha256$...)
        from passlib.context import CryptContext
        pwd_ctx = CryptContext(schemes=["pbkdf2_sha256"])

        password = "LegacyPass789!"
        hashed = pwd_ctx.hash(password)

        # Verify format (passlib uses $pbkdf2-sha256$...)
        assert hashed.startswith("$pbkdf2-sha256$"), f"Expected passlib format, got: {hashed[:20]}..."

        # Our hybrid verifier should handle this
        assert verify_password(password, hashed) is True
        assert verify_password("WrongPass", hashed) is False

    def test_mixed_hash_scenarios(self):
        """Test that both hash types coexist and work independently."""
        password1 = "PasswordForBcrypt123!"
        password2 = "LegacyPassphrase456!"

        bcrypt_hash = get_password_hash(password1)  # bcrypt

        # Manually create passlib hash for password2
        from passlib.context import CryptContext
        pwd_ctx = CryptContext(schemes=["pbkdf2_sha256"])
        passlib_hash = pwd_ctx.hash(password2)

        # Verify each password against its own hash
        assert verify_password(password1, bcrypt_hash) is True
        assert verify_password(password2, passlib_hash) is True

        # Verify cross-failure (wrong password)
        assert verify_password("Wrong", bcrypt_hash) is False
        assert verify_password("Wrong", passlib_hash) is False

    def test_empty_hash_handling(self):
        """Test that empty or None hashes return False safely."""
        assert verify_password("password", "") is False
        assert verify_password("password", None) is False  # type: ignore

    def test_corrupted_bcrypt_hash(self):
        """Test that malformed bcrypt hashes are handled gracefully."""
        # Truncated bcrypt hash
        bad_hash = "$2b$12$invalidtruncatedhash"
        assert verify_password("password", bad_hash) is False

    def test_unicode_passwords(self):
        """Test that unicode passwords work with bcrypt."""
        password = "Pässwörd€123🔒"
        hashed = get_password_hash(password)
        assert verify_password(password, hashed) is True

    def test_long_passwords(self):
        """Test that very long passwords are handled correctly."""
        password = "A" * 200  # Bcrypt supports up to 72 bytes, but we encode utf-8
        hashed = get_password_hash(password)
        assert verify_password(password, hashed) is True

    def test_migration_on_password_change(self):
        """
        Simulate user login with legacy hash, then password change upgrades to bcrypt.
        This is the actual migration strategy.
        """
        from passlib.context import CryptContext

        # 1. User has legacy passlib hash in DB
        old_password = "OldLegacyPass123!"
        pwd_ctx = CryptContext(schemes=["pbkdf2_sha256"])
        legacy_hash = pwd_ctx.hash(old_password)

        # 2. User logs in successfully with legacy hash
        assert verify_password(old_password, legacy_hash) is True

        # 3. User changes password (new hash is bcrypt)
        new_password = "NewStrongBcryptPass456!"
        new_hash = get_password_hash(new_password)

        # 4. New hash is bcrypt format
        assert new_hash.startswith('$2b$') or new_hash.startswith('$2a$')

        # 5. New password verifies with new hash
        assert verify_password(new_password, new_hash) is True

        # 6. Old password no longer works with new hash
        assert verify_password(old_password, new_hash) is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
