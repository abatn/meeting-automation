from typing import Optional
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from fastapi.security import OAuth2PasswordBearer
import bcrypt
from passlib.context import CryptContext
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")

# Keep passlib for backward compatibility with existing password hashes
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify password against hash with hybrid support.

    Supports:
    - bcrypt hashes (new format, starting with $2b$, $2a$, $2y$)
    - passlib/pbkdf2_sha256 hashes (legacy format)

    Migration strategy:
    - Existing passlib hashes continue to work
    - New passwords are hashed with bcrypt (stronger)
    - When user changes password, it automatically upgrades to bcrypt
    """
    if not hashed_password:
        return False

    # Detect bcrypt format (starts with $2b$, $2a$, or $2y$)
    is_bcrypt = hashed_password.startswith(('$2b$', '$2a$', '$2y$'))

    try:
        if is_bcrypt:
            result = bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
            # Log hash type for migration tracking (debug level)
            logger.debug(f"Password verified with bcrypt hash (user_id from token)")
            return result
        else:
            # Assume passlib/pbkdf2_sha256 legacy hash
            result = pwd_context.verify(plain_password, hashed_password)
            logger.debug(f"Password verified with legacy passlib hash (migration in progress)")
            return result
    except Exception as e:
        logger.error(f"Password verification error: {e}")
        return False


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt (current standard)."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": int(expire.timestamp())})
    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return encoded_jwt


def verify_token(token: str):
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        return payload
    except JWTError:
        return None
