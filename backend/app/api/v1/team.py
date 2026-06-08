from typing import List, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api import deps
from app.models.user import User as UserModel, UserRole
from app.schemas.team import TeamMember, TeamMemberCreate, TeamMemberUpdate, TeamSearchResult
from app.services.team_service import TeamService

router = APIRouter()

@router.get("/", response_model=List[TeamMember])
async def list_team_members(
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.check_permissions([UserRole.DG, UserRole.MANAGER])),
) -> Any:
    """List all team members for the client. DG and Manager only."""
    service = TeamService(db)
    return await service.get_team_members(current_user.client_id)

@router.post("/", response_model=TeamMember)
async def create_team_member(
    member_in: TeamMemberCreate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.check_permissions([UserRole.DG, UserRole.MANAGER])),
) -> Any:
    """Create a new team member. DG and Manager only."""
    service = TeamService(db)
    try:
        return await service.create_team_member(current_user.client_id, member_in, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.patch("/{member_id}")
async def update_team_member(
    member_id: str,
    member_in: TeamMemberUpdate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.check_permissions([UserRole.DG, UserRole.MANAGER])),
) -> Any:
    """Update a team member or user. DG and Manager only."""
    service = TeamService(db)
    member = await service.update_team_member(current_user.client_id, member_id, member_in, current_user.id)
    if not member:
        raise HTTPException(status_code=404, detail="Team member not found")
    return member

@router.delete("/{member_id}")
async def delete_team_member(
    member_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.check_permissions([UserRole.DG, UserRole.MANAGER])),
) -> Any:
    """Delete a team member. DG and Manager only."""
    service = TeamService(db)
    success = await service.delete_team_member(current_user.client_id, member_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Team member not found")
    return {"status": "deleted"}

@router.get("/search", response_model=List[TeamSearchResult])
async def search_team(
    q: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.check_permissions([UserRole.DG, UserRole.MANAGER])),
) -> Any:
    """Search across users and team members for the planner. DG and Manager only."""
    service = TeamService(db)
    return await service.search_members(current_user.client_id, q)
