from typing import Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr
from app.models.user import UserStatus


class UserBase(BaseModel):
    client_id: Optional[str] = None
    email: EmailStr
    full_name: Optional[str] = None
    status: Optional[UserStatus] = UserStatus.ACTIVE
    role: Optional[str] = "participant"
    department: Optional[str] = None


class UserCreate(UserBase):
    password: str
    company_name: Optional[str] = None
    plan: Optional[str] = "GRATUIT"


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    password: Optional[str] = None
    status: Optional[UserStatus] = None
    role: Optional[str] = None
    department: Optional[str] = None


class UserInDBBase(UserBase):
    id: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    is_superuser: bool = False  # Added
    is_mfa_enabled: bool = False  # Added

    class Config:
        from_attributes = True


class User(UserInDBBase):
    pass


class UserInDB(UserInDBBase):
    hashed_password: str


class Token(BaseModel):
    access_token: str
    token_type: str
    user: User


class TokenData(BaseModel):
    user_id: Optional[str] = None

class ActivationConfirm(BaseModel):
    token: str
    new_password: str
