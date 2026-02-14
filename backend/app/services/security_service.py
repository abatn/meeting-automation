from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import Optional, List
from app.models.user import User, UserRole
from app.schemas.user import UserCreate, UserUpdate
from app.core.security import get_password_hash, verify_password
import pyotp
import qrcode
import io
import base64

async def get_user_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
    """Holt einen Benutzer anhand der ID."""
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()

async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    """Holt einen Benutzer anhand der Email."""
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()

async def get_user_by_username(db: AsyncSession, username: str) -> Optional[User]:
    """Holt einen Benutzer anhand des Usernames."""
    result = await db.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()

async def get_users(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[User]:
    """Holt eine Liste aller Benutzer."""
    result = await db.execute(select(User).offset(skip).limit(limit))
    return result.scalars().all()

async def create_user(db: AsyncSession, user_data: UserCreate) -> User:
    """Erstellt einen neuen Benutzer."""
    hashed_password = get_password_hash(user_data.password)
    db_user = User(
        email=user_data.email,
        username=user_data.username,
        hashed_password=hashed_password,
        full_name=user_data.full_name,
        role=UserRole(user_data.role) if user_data.role else UserRole.PARTICIPANT
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user

async def update_user(db: AsyncSession, user_id: int, user_data: UserUpdate) -> Optional[User]:
    """Aktualisiert einen Benutzer."""
    user = await get_user_by_id(db, user_id)
    if not user:
        return None
    
    update_data = user_data.dict(exclude_unset=True)
    if "password" in update_data:
        update_data["hashed_password"] = get_password_hash(update_data.pop("password"))
    
    for field, value in update_data.items():
        setattr(user, field, value)
    
    await db.commit()
    await db.refresh(user)
    return user

async def delete_user(db: AsyncSession, user_id: int) -> bool:
    """Löscht einen Benutzer."""
    user = await get_user_by_id(db, user_id)
    if not user:
        return False
    
    await db.delete(user)
    await db.commit()
    return True

async def authenticate_user(db: AsyncSession, username: str, password: str) -> Optional[User]:
    """Authentifiziert einen Benutzer."""
    user = await get_user_by_username(db, username)
    if not user:
        user = await get_user_by_email(db, username)
    
    if not user or not verify_password(password, user.hashed_password):
        return None
    
    return user

# MFA-Funktionen
def generate_mfa_secret() -> str:
    """Generiert ein MFA-Secret."""
    return pyotp.random_base32()

def get_mfa_provisioning_uri(secret: str, email: str) -> str:
    """Generiert die Provisioning-URI für Google Authenticator."""
    return pyotp.totp.TOTP(secret).provisioning_uri(email, issuer_name="Meeting Automation")

def generate_qr_code_base64(uri: str) -> str:
    """Generiert einen QR-Code als Base64-String."""
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()

def verify_mfa_code(secret: str, code: str) -> bool:
    """Verifiziert einen MFA-Code."""
    totp = pyotp.TOTP(secret)
    return totp.verify(code)