from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated, List

from backend.app.api import deps
from backend.app.core.database import get_db
from backend.app.models.user import User, UserRole
from backend.app.schemas.user import UserCreate, UserUpdate, UserResponse
from backend.app.services.security_service import security_service
from backend.app.services.audit_service import AuditService
from backend.app.schemas.audit import AuditLogCreate

router = APIRouter()
audit_service = AuditService()

@router.post("/", response_model=UserResponse)
async def create_user(
    request: Request,
    user_in: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """
    Create a new user.
    """
    user = await security_service.get_user_by_email(db, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=400,
            detail="Email already registered",
        )
    user = await security_service.get_user_by_username(db, username=user_in.username)
    if user:
        raise HTTPException(
            status_code=400,
            detail="Username already registered",
        )
    
    user = await security_service.create_user(db, user_in)
    
    # Audit Log
    await audit_service.log_action(
        db=db,
        log_data=AuditLogCreate(
            user_id=user.id,
            action="CREATE_USER",
            method=request.method,
            path=request.url.path,
            resource_type="user",
            resource_id=user.id,
            details={"email": user.email, "username": user.username},
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent")
        )
    )
    
    return user

@router.get("/me", response_model=UserResponse)
async def read_user_me(
    current_user: Annotated[User, Depends(deps.get_current_active_user)]
):
    """
    Get current user.
    """
    return current_user

@router.put("/me", response_model=UserResponse)
async def update_user_me(
    request: Request,
    user_in: UserUpdate,
    current_user: Annotated[User, Depends(deps.get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """
    Update current user.
    """
    if user_in.email and user_in.email != current_user.email:
        user = await security_service.get_user_by_email(db, email=user_in.email)
        if user:
            raise HTTPException(
                status_code=400,
                detail="Email already registered",
            )
            
    if user_in.username and user_in.username != current_user.username:
        user = await security_service.get_user_by_username(db, username=user_in.username)
        if user:
            raise HTTPException(
                status_code=400,
                detail="Username already registered",
            )

    user = await security_service.update_user(db, current_user.id, user_in)
    
    # Audit Log
    await audit_service.log_action(
        db=db,
        log_data=AuditLogCreate(
            user_id=user.id,
            action="UPDATE_USER_ME",
            method=request.method,
            path=request.url.path,
            resource_type="user",
            resource_id=user.id,
            details=user_in.dict(exclude_unset=True),
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent")
        )
    )
    
    return user

@router.get("/", response_model=List[UserResponse])
async def read_users(
    current_user: Annotated[User, Depends(deps.get_current_active_superuser)],
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: int = 0,
    limit: int = 100
):
    """
    Retrieve users.
    """
    users = await security_service.get_users(db, skip=skip, limit=limit)
    return users

@router.get("/{user_id}", response_model=UserResponse)
async def read_user_by_id(
    user_id: int,
    current_user: Annotated[User, Depends(deps.get_current_active_superuser)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """
    Get a specific user by id.
    """
    user = await security_service.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )
    return user

@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    request: Request,
    user_id: int,
    user_in: UserUpdate,
    current_user: Annotated[User, Depends(deps.get_current_active_superuser)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """
    Update a user.
    """
    user = await security_service.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )
        
    if user_in.email and user_in.email != user.email:
        existing_user = await security_service.get_user_by_email(db, email=user_in.email)
        if existing_user:
            raise HTTPException(
                status_code=400,
                detail="Email already registered",
            )
            
    if user_in.username and user_in.username != user.username:
        existing_user = await security_service.get_user_by_username(db, username=user_in.username)
        if existing_user:
            raise HTTPException(
                status_code=400,
                detail="Username already registered",
            )

    user = await security_service.update_user(db, user.id, user_in)
    
    # Audit Log
    await audit_service.log_action(
        db=db,
        log_data=AuditLogCreate(
            user_id=current_user.id,
            action="UPDATE_USER",
            method=request.method,
            path=request.url.path,
            resource_type="user",
            resource_id=user.id,
            details=user_in.dict(exclude_unset=True),
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent")
        )
    )
    
    return user

@router.delete("/{user_id}")
async def delete_user(
    request: Request,
    user_id: int,
    current_user: Annotated[User, Depends(deps.get_current_active_superuser)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """
    Delete a user.
    """
    user = await security_service.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )
        
    await security_service.delete_user(db, user_id)
    
    # Audit Log
    await audit_service.log_action(
        db=db,
        log_data=AuditLogCreate(
            user_id=current_user.id,
            action="DELETE_USER",
            method=request.method,
            path=request.url.path,
            resource_type="user",
            resource_id=user_id,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent")
        )
    )
    
    return {"message": "User deleted successfully"}