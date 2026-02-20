from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from app.api import deps
from app.schemas.user import User, UserCreate, Token
from app.services.security_service import SecurityService
from datetime import timedelta
from app.core.config import settings

router = APIRouter()

@router.post("/login", response_model=Token)
async def login(
    db: AsyncSession = Depends(deps.get_db),
    form_data: OAuth2PasswordRequestForm = Depends()
):
    # Mocking user authentication for setup
    # In production: user = await user_service.authenticate(...)
    if form_data.username != "admin@example.com" or form_data.password != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = SecurityService.create_access_token(
        subject="1", # Mock User ID
        expires_delta=access_token_expires
    )
    refresh_token = SecurityService.create_refresh_token(subject="1")
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }

@router.post("/register", response_model=User)
async def register(
    user_in: UserCreate,
    db: AsyncSession = Depends(deps.get_db)
):
    # Mock registration
    return User(
        id=1,
        email=user_in.email,
        full_name=user_in.full_name,
        is_active=True,
        role="participant"
    )

@router.get("/me", response_model=User)
async def get_me(current_user: User = Depends(deps.get_current_user)):
    return current_user