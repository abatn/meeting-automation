import uuid
import logging
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, delete
from app.models.team import TeamMember
from app.models.user import User
from app.schemas.team import TeamMemberCreate, TeamMemberUpdate, TeamSearchResult
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)

class TeamService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_team_members(self, client_id: str) -> List[TeamMember]:
        """Get all team members for a client."""
        stmt = select(TeamMember).where(TeamMember.client_id == client_id).order_by(TeamMember.full_name)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def create_team_member(self, client_id: str, obj_in: TeamMemberCreate, creator_id: str) -> TeamMember:
        """Create a new team member."""
        db_obj = TeamMember(
            id=str(uuid.uuid4()),
            client_id=client_id,
            **obj_in.model_dump()
        )
        self.db.add(db_obj)
        await self.db.commit()
        await self.db.refresh(db_obj)
        
        # Audit Log (ISO 27001) - Fix: use 'new_values' instead of 'details'
        await AuditService.log_action(
            self.db, 
            client_id=client_id, 
            action="CREATE_TEAM_MEMBER", 
            user_id=creator_id,
            table_name="team_members",
            record_id=db_obj.id,
            new_values={"email": db_obj.email, "full_name": db_obj.full_name}
        )
        
        return db_obj

    async def update_team_member(self, client_id: str, member_id: str, obj_in: TeamMemberUpdate, user_id: str) -> Optional[TeamMember]:
        """Update a team member."""
        stmt = select(TeamMember).where(TeamMember.id == member_id, TeamMember.client_id == client_id)
        result = await self.db.execute(stmt)
        db_obj = result.scalar_one_or_none()
        
        if not db_obj:
            return None
            
        update_data = obj_in.model_dump(exclude_unset=True)
        for field in update_data:
            setattr(db_obj, field, update_data[field])
            
        await self.db.commit()
        await self.db.refresh(db_obj)
        
        # Audit Log (ISO 27001)
        await AuditService.log_action(
            self.db, 
            client_id=client_id, 
            action="UPDATE_TEAM_MEMBER", 
            user_id=user_id,
            table_name="team_members",
            record_id=member_id,
            new_values=update_data
        )
        
        return db_obj

    async def delete_team_member(self, client_id: str, member_id: str, user_id: str) -> bool:
        """Delete a team member."""
        stmt = delete(TeamMember).where(TeamMember.id == member_id, TeamMember.client_id == client_id)
        result = await self.db.execute(stmt)
        await self.db.commit()
        
        # Audit Log (ISO 27001)
        if result.rowcount > 0:
            await AuditService.log_action(
                self.db, 
                client_id=client_id, 
                action="DELETE_TEAM_MEMBER", 
                user_id=user_id,
                table_name="team_members",
                record_id=member_id
            )
        
        return result.rowcount > 0

    async def search_members(self, client_id: str, query: str) -> List[TeamSearchResult]:
        """Search across both registered Users and TeamMembers."""
        results = []
        
        # 1. Search Users
        user_stmt = select(User).where(
            User.client_id == client_id,
            or_(
                User.full_name.ilike(f"%{query}%"),
                User.email.ilike(f"%{query}%")
            )
        ).limit(10)
        user_res = await self.db.execute(user_stmt)
        for u in user_res.scalars().all():
            results.append(TeamSearchResult(
                id=u.id,
                full_name=u.full_name or u.email,
                email=u.email,
                source="user"
            ))
            
        # 2. Search TeamMembers
        team_stmt = select(TeamMember).where(
            TeamMember.client_id == client_id,
            or_(
                TeamMember.full_name.ilike(f"%{query}%"),
                TeamMember.email.ilike(f"%{query}%")
            )
        ).limit(10)
        team_res = await self.db.execute(team_stmt)
        for t in team_res.scalars().all():
            # Avoid duplicates if someone is both a user and a team member
            if not any(r.email == t.email for r in results):
                results.append(TeamSearchResult(
                    id=t.id,
                    full_name=t.full_name,
                    email=t.email,
                    source="team_member",
                    position=t.position,
                    department=t.department
                ))
                
        return results
