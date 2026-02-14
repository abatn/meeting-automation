from typing import Optional, Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from jose import JWTError
from app.core.database import get_db
from app.core.security import verify_token
from app.models.user import User
from app.services.security_service import get_user_by_id

# OAuth2 Schema für Token-Authentifizierung
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)]
) -> User:
    """Extrahiert den aktuellen Benutzer aus dem JWT Token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # Token verifizieren
    payload = verify_token(token)
    if payload is None:
        raise credentials_exception
    
    user_id: str = payload.get("sub")
    if user_id is None:
        raise credentials_exception
    
    # Benutzer aus Datenbank laden
    user = await get_user_by_id(db, int(user_id))
    if user is None:
        raise credentials_exception
    
    db.expunge(user)  # Detach the user object from the session
    return user

async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)]
) -> User:
    """Stellt sicher, dass der Benutzer aktiv ist."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user

# Rollen-basierte Berechtigungen
def require_role(required_role: str):
    """Dependency, die eine bestimmte Rolle verlangt."""
    async def role_checker(
        current_user: Annotated[User, Depends(get_current_active_user)]
    ) -> User:
        if current_user.role.value != required_role and current_user.role.value != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role {required_role} required"
            )
        return current_user
    return role_checker

# Spezifische Rollen-Dependencies
require_admin = require_role("admin")
require_dg = require_role("dg")
require_manager = require_role("manager")