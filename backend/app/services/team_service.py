import uuid
import secrets
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, delete
from app.models.team import TeamMember
from app.models.user import User, UserStatus, ActivationToken, Role
from app.models.client import Client
from app.schemas.team import TeamMemberCreate, TeamMemberUpdate, TeamSearchResult
from app.services.audit_service import AuditService
from app.utils.webhook_utils import trigger_user_invited_webhook
from app.core.config import settings
from app.core import security

logger = logging.getLogger(__name__)

class TeamService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_team_members(self, client_id: str) -> List[dict]:
        """Get all team members and pending users for a client. Excludes disabled users."""
        # 1. Fetch ALL Users for this client to handle filtering and de-duplication
        user_stmt = select(User).where(User.client_id == client_id).order_by(User.full_name)
        user_res = await self.db.execute(user_stmt)
        all_users = user_res.scalars().all()
        
        # 2. Fetch TeamMembers
        team_stmt = select(TeamMember).where(TeamMember.client_id == client_id).order_by(TeamMember.full_name)
        team_res = await self.db.execute(team_stmt)
        team_members = team_res.scalars().all()

        results = []
        user_emails = set()
        disabled_emails = set()
        
        for u in all_users:
            user_emails.add(u.email)
            if u.status == UserStatus.DISABLED.value:
                disabled_emails.add(u.email)
                continue
                
            results.append({
                "id": u.id,
                "client_id": u.client_id,
                "full_name": u.full_name or u.email,
                "email": u.email,
                "status": u.status, # ACTIVE, PENDING
                "role": u.role,
                "position": "User",
                "department": None,
                "created_at": u.created_at,
                "source": "user"
            })
            
        for t in team_members:
            # Only add if not already a registered User (active or disabled)
            if t.email not in user_emails:
                results.append({
                    "id": t.id,
                    "client_id": t.client_id,
                    "full_name": t.full_name,
                    "email": t.email,
                    "status": "TEAM_MEMBER",
                    "role": "participant",
                    "position": t.position,
                    "department": t.department,
                    "created_at": t.created_at,
                    "source": "team_member"
                })
        return results

    async def create_team_member(self, client_id: str, obj_in: TeamMemberCreate, creator_id: str) -> User:
        """Invite a new team member. Re-activates if user was previously DISABLED."""
        # Security: Prevent assigning global admin roles via team management
        if obj_in.role in ["system_admin", "tech_admin"]:
            raise ValueError("Unauthorized role assignment.")

        # Check if email exists in Users
        stmt = select(User).where(User.email == obj_in.email)
        res = await self.db.execute(stmt)
        existing_user = res.scalar_one_or_none()
        
        if existing_user:
            if existing_user.status != UserStatus.DISABLED.value:
                raise ValueError("A user with this email already exists and is active or pending.")
            
            # Re-activate the DISABLED user
            existing_user.status = UserStatus.PENDING.value
            existing_user.deleted_at = None  # Clear soft-delete for ISO 27001 compliance
            existing_user.full_name = obj_in.full_name
            # Secure random placeholder password (user will set via activation)
            existing_user.hashed_password = security.get_password_hash(secrets.token_urlsafe(32))
            new_user = existing_user
            
            # Delete old tokens if any exist
            await self.db.execute(delete(ActivationToken).where(ActivationToken.user_id == new_user.id))
            await self.db.flush()
        else:
            # Check if email exists in TeamMember and remove to upgrade them
            stmt_tm = select(TeamMember).where(TeamMember.email == obj_in.email, TeamMember.client_id == client_id)
            res_tm = await self.db.execute(stmt_tm)
            existing_tm = res_tm.scalar_one_or_none()
            if existing_tm:
                 await self.db.delete(existing_tm)
                 await self.db.flush()

            # Create new PENDING User
            new_user = User(
                id=str(uuid.uuid4()),
                client_id=client_id,
                email=obj_in.email,
                full_name=obj_in.full_name,
                # Secure random placeholder password (user will set via activation)
                hashed_password=security.get_password_hash(secrets.token_urlsafe(32)),
                status=UserStatus.PENDING.value,
                is_superuser=False,
                is_mfa_enabled=False
            )
            # We don't add to DB yet, we assign roles first

        # Update / Assign role
        role_stmt = select(Role).where(Role.name == obj_in.role)
        role_res = await self.db.execute(role_stmt)
        role_obj = role_res.scalar_one_or_none()
        
        if not role_obj:
            # Fallback to participant if role doesn't exist
            role_stmt = select(Role).where(Role.name == "participant")
            role_res = await self.db.execute(role_stmt)
            role_obj = role_res.scalar_one()

        # Explicitly set the roles list to avoid lazy loading issues
        new_user.roles = [role_obj]
        
        if not existing_user:
            self.db.add(new_user)
            
        await self.db.flush()

        # Create New Activation Token
        token = secrets.token_urlsafe(32)
        expiration = datetime.now(timezone.utc) + timedelta(days=7)
        activation_entry = ActivationToken(
            id=str(uuid.uuid4()),
            user_id=new_user.id,
            token=token,
            expires_at=expiration
        )
        self.db.add(activation_entry)
        
        # Get Client name
        client_stmt = select(Client).where(Client.id == client_id)
        client_res = await self.db.execute(client_stmt)
        client_obj = client_res.scalar_one()

        await self.db.commit()
        await self.db.refresh(new_user)
        
        # Trigger Webhook
        activation_link = f"{settings.FRONTEND_URL}/activate?token={token}"
        await trigger_user_invited_webhook(
            email=new_user.email,
            full_name=new_user.full_name or "Colleague",
            company_name=client_obj.company_name,
            activation_link=activation_link
        )

        # Audit Log
        await AuditService.log_action(
            self.db, 
            client_id=client_id, 
            action="RE_INVITE_USER" if existing_user else "INVITE_USER", 
            user_id=creator_id,
            table_name="users",
            record_id=new_user.id,
            new_values={"email": new_user.email, "status": new_user.status}
        )
        
        return new_user

    async def update_team_member(self, client_id: str, member_id: str, obj_in: TeamMemberUpdate, user_id: str) -> Optional[dict]:
        """Update a team member or user. Handles both team_members and users tables."""
        # Security: Prevent assigning global admin roles via team management
        if obj_in.role and obj_in.role in ["system_admin", "tech_admin"]:
            raise ValueError("Unauthorized role assignment.")

        # 1. Try to update TeamMember (legacy - not yet registered)
        stmt = select(TeamMember).where(TeamMember.id == member_id, TeamMember.client_id == client_id)
        result = await self.db.execute(stmt)
        db_obj = result.scalar_one_or_none()

        if db_obj:
            update_data = obj_in.model_dump(exclude_unset=True)
            old_values = {field: getattr(db_obj, field, None) for field in update_data}

            for field in update_data:
                setattr(db_obj, field, update_data[field])

            await self.db.commit()
            await self.db.refresh(db_obj)

            # Audit Log (ISO 27001 A.12.4.1)
            await AuditService.log_action(
                self.db,
                client_id=client_id,
                action="UPDATE_TEAM_MEMBER",
                user_id=user_id,
                table_name="team_members",
                record_id=member_id,
                old_values=old_values,
                new_values=update_data
            )

            return {
                "id": db_obj.id,
                "client_id": db_obj.client_id,
                "full_name": db_obj.full_name,
                "email": db_obj.email,
                "status": "TEAM_MEMBER",
                "role": "participant",
                "position": db_obj.position,
                "department": db_obj.department,
                "created_at": db_obj.created_at,
                "source": "team_member"
            }

        # 2. Try to update User (registered user with active/pending account)
        user_stmt = select(User).where(User.id == member_id, User.client_id == client_id)
        user_res = await self.db.execute(user_stmt)
        db_user = user_res.scalar_one_or_none()

        if db_user:
            update_data = obj_in.model_dump(exclude_unset=True)
            old_values = {
                "full_name": db_user.full_name,
                "role": db_user.role,
            }

            # Update full_name if provided
            if "full_name" in update_data:
                db_user.full_name = update_data["full_name"]

            # Update role if provided (via user_roles relationship)
            if "role" in update_data:
                role_stmt = select(Role).where(Role.name == update_data["role"])
                role_res = await self.db.execute(role_stmt)
                new_role = role_res.scalar_one_or_none()

                if new_role:
                    db_user.roles = [new_role]
                else:
                    # Fallback to participant if role doesn't exist
                    role_stmt = select(Role).where(Role.name == "participant")
                    role_res = await self.db.execute(role_stmt)
                    db_user.roles = [role_res.scalar_one()]

            await self.db.commit()
            await self.db.refresh(db_user)

            # Audit Log (ISO 27001 A.12.4.1) - Role change is security-relevant!
            await AuditService.log_action(
                self.db,
                client_id=client_id,
                action="UPDATE_USER_ROLE",
                user_id=user_id,
                table_name="users",
                record_id=member_id,
                old_values=old_values,
                new_values={
                    "full_name": db_user.full_name,
                    "role": db_user.role,
                }
            )

            return {
                "id": db_user.id,
                "client_id": db_user.client_id,
                "full_name": db_user.full_name or db_user.email,
                "email": db_user.email,
                "status": db_user.status,
                "role": db_user.role,
                "position": "User",
                "department": None,
                "created_at": db_user.created_at,
                "source": "user"
            }

        return None

    async def delete_team_member(self, client_id: str, member_id: str, user_id: str) -> bool:
        """Delete a team member or disable a User."""
        # 1. Try to delete TeamMember
        stmt = delete(TeamMember).where(TeamMember.id == member_id, TeamMember.client_id == client_id)
        result = await self.db.execute(stmt)
        
        if result.rowcount > 0:
            await self.db.commit()
            await AuditService.log_action(
                self.db, 
                client_id=client_id, 
                action="DELETE_TEAM_MEMBER", 
                user_id=user_id,
                table_name="team_members",
                record_id=member_id
            )
            return True
            
        # 2. Try to disable User instead of deleting to preserve Audit Logs
        user_stmt = select(User).where(User.id == member_id, User.client_id == client_id)
        user_res = await self.db.execute(user_stmt)
        db_user = user_res.scalar_one_or_none()
        
        if db_user:
            from datetime import datetime
            db_user.status = UserStatus.DISABLED.value
            db_user.deleted_at = datetime.now(timezone.utc)  # Soft-delete for ISO 27001 compliance
            # Also cascade delete any tokens if pending
            token_stmt = delete(ActivationToken).where(ActivationToken.user_id == db_user.id)
            await self.db.execute(token_stmt)
            
            await self.db.commit()
            await AuditService.log_action(
                self.db, 
                client_id=client_id, 
                action="DISABLE_USER", 
                user_id=user_id,
                table_name="users",
                record_id=member_id
            )
            return True

        return False

    async def search_members(self, client_id: str, query: str) -> List[TeamSearchResult]:
        """Search across both registered Users and TeamMembers. Excludes disabled users."""
        results = []
        
        # 1. Search Users (Exclude DISABLED)
        user_stmt = select(User).where(
            User.client_id == client_id,
            User.status != UserStatus.DISABLED.value,
            or_(
                User.full_name.ilike(f"%{query}%"),
                User.email.ilike(f"%{query}%")
            )
        ).limit(10)
        user_res = await self.db.execute(user_stmt)
        user_emails = set()
        for u in user_res.scalars().all():
            user_emails.add(u.email)
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
            # Avoid duplicates and don't add if a registered User (active or disabled) already exists
            if t.email not in user_emails:
                # Still check for all users to be sure about disabled status
                check_user_stmt = select(User).where(User.email == t.email, User.client_id == client_id)
                check_user_res = await self.db.execute(check_user_stmt)
                if check_user_res.scalar_one_or_none():
                    continue

                results.append(TeamSearchResult(
                    id=t.id,
                    full_name=t.full_name,
                    email=t.email,
                    source="team_member",
                    position=t.position,
                    department=t.department
                ))
                
        return results
