"""Utilities for secure token handling."""

import hashlib
from typing import Optional


def hash_token(token: str) -> str:
    """
    Hash a token using SHA-256 for secure storage.

    Args:
        token: The plaintext token to hash

    Returns:
        The hexadecimal SHA-256 hash of the token
    """
    return hashlib.sha256(token.encode()).hexdigest()


def verify_token(provided_token: str, stored_hash: Optional[str], legacy_token: Optional[str] = None) -> bool:
    """
    Verify a token against its stored hash.

    Supports both new (hash-based) and legacy (plaintext) tokens for backward compatibility.

    Args:
        provided_token: The token provided by the user
        stored_hash: The stored SHA-256 hash of the token (for new tokens)
        legacy_token: The stored plaintext token (for backward compatibility with old tokens)

    Returns:
        True if token matches either the hash or legacy plaintext
    """
    # Check new hash-based storage first
    if stored_hash:
        return hash_token(provided_token) == stored_hash

    # Fall back to legacy plaintext comparison (for tokens created before hashing was implemented)
    if legacy_token:
        return provided_token == legacy_token

    return False
