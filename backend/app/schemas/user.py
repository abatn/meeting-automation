from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime

class UserBase(BaseModel):
    email: EmailStr
    username: str
    full_name: Optional[str] = None

class UserCreate(UserBase):
    password: str
    role: Optional[str] = None

class UserUpdate(UserBase):
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    password: Optional[str] = None
    full_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    is_mfa_enabled: Optional[bool] = None

class UserResponse(UserBase):
    id: int
    role: str
    is_active: bool
    is_superuser: bool
    is_mfa_enabled: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {'from_attributes': True}

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    requires_mfa: bool = False
    user_id: Optional[int] = None

class MFASetupResponse(BaseModel):
    secret: str
    qr_code: str
    uri: str

class MFACode(BaseModel):
    user_id: int
    code: str = Field(..., min_length=6, max_length=6)
