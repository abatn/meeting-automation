from typing import Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr, field_validator
from app.models.user import UserStatus
from app.utils.password_validation import validate_password


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
    consents: list = []
    
    @field_validator('password')
    @classmethod
    def validate_password_strength(cls, v):
        is_valid, errors = validate_password(v)
        if not is_valid:
            raise ValueError(', '.join(errors))
        return v


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
    subscription_plan: Optional[str] = None

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
    
    @field_validator('new_password')
    @classmethod
    def validate_password_strength(cls, v):
        is_valid, errors = validate_password(v)
        if not is_valid:
            raise ValueError(', '.join(errors))
        return v
