"""
Phase 2 E2E Tests: Team Management & Meeting Authorization

Tests for:
- P2-1: Email conflict resolution (users vs team_members)
- P2-2: Secure PENDING password for invited users
- P2-3: Meeting update authorization (creator/admin/dg only)
- P2-4: DB constraint: end_time > start_time
- P2-5: Unique constraint: participants(meeting_id, email)

Date: 2026-05-05
"""
import pytest
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import User, UserStatus, ActivationToken, Role
from app.models.client import Client
from app.models.team import TeamMember
from app.models.meeting import Meeting, Participant
from app.core import security
from app.schemas.team import TeamMemberCreate
from app.schemas.meeting import MeetingCreate, ParticipantCreate, AgendaCreate, MeetingUpdate
from app.services.team_service import TeamService
from app.services.meeting_service import MeetingService


@pytest.mark.asyncio
async def test_p21_register_deletes_existing_team_member(client: AsyncClient, db_session: AsyncSession):
    """P2-1: Self-service registration should delete existing TeamMember with same email"""
    # 1. Create client first
    client_obj = Client(
        id=str(uuid.uuid4()),
        company_name=f"TestCorp-{uuid.uuid4()}",
        subscription_plan="GRATUIT",
        subscription_status="ACTIVE",
        minutes_included=600
    )
    db_session.add(client_obj)
    await db_session.flush()

    # 2. Create TeamMember
    team_member = TeamMember(
        id=str(uuid.uuid4()),
        client_id=client_obj.id,
        email=f"upgrade_{uuid.uuid4()}@example.com",
        full_name="Future User",
        position="Developer",
        department="Engineering"
    )
    db_session.add(team_member)
    await db_session.commit()

    # 3. Self-service register with same email
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": team_member.email,
            "password": "SecurePass123!",
            "full_name": "Future User",
            "company_name": "TestCorp"
        }
    )
    assert response.status_code == 201, f"Register failed: {response.text}"

    # 4. Verify TeamMember was deleted (upgraded to User)
    tm_stmt = select(TeamMember).where(TeamMember.email == team_member.email)
    tm_res = await db_session.execute(tm_stmt)
    deleted_tm = tm_res.scalar_one_or_none()
    assert deleted_tm is None, "TeamMember should be deleted after registration"

    # 5. Verify User was created with PENDING status
    user_stmt = select(User).where(User.email == team_member.email)
    user_res = await db_session.execute(user_stmt)
    new_user = user_res.scalar_one_or_none()
    assert new_user is not None, "User should exist"
    assert new_user.status == UserStatus.PENDING.value, "User should be PENDING"


@pytest.mark.asyncio
async def test_p21_register_rejects_duplicate_email(client: AsyncClient, db_session: AsyncSession):
    """P2-1: Self-service registration should reject duplicate email in users table"""
    # 1. Create first user
    response1 = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "duplicate@example.com",
            "password": "SecurePass123!",
            "full_name": "First User",
            "company_name": "TestCorp1"
        }
    )
    assert response1.status_code == 201

    # 2. Try to register with same email
    response2 = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "duplicate@example.com",
            "password": "SecurePass123!",
            "full_name": "Second User",
            "company_name": "TestCorp2"
        }
    )
    assert response2.status_code == 400, "Should reject duplicate email"
    assert "already exists" in response2.json()["detail"]


@pytest.mark.asyncio
async def test_p22_team_member_has_secure_placeholder_password(db_session: AsyncSession):
    """P2-2: Invited team members should have secure random hashed password"""
    # Create client
    client_obj = Client(
        id=str(uuid.uuid4()),
        company_name=f"TestCorp-{uuid.uuid4()}",
        subscription_plan="GRATUIT",
        subscription_status="ACTIVE",
        minutes_included=600
    )
    db_session.add(client_obj)
    await db_session.flush()

    # Add admin role
    role_stmt = select(Role).where(Role.name == "admin")
    role_res = await db_session.execute(role_stmt)
    admin_role = role_res.scalar_one()

    # Create admin user with role assigned at creation
    admin_user = User(
        id=str(uuid.uuid4()),
        client_id=client_obj.id,
        email="admin@example.com",
        full_name="Admin User",
        hashed_password=security.get_password_hash("Password123!"),
        status=UserStatus.ACTIVE.value,
        is_superuser=False,
        is_mfa_enabled=False,
        roles=[admin_role],
    )
    db_session.add(admin_user)
    await db_session.commit()

    # Invite team member via TeamService
    team_service = TeamService(db_session)
    team_member_data = TeamMemberCreate(
        email="invite@example.com",
        full_name="Invited User",
        role="participant"
    )
    invited_user = await team_service.create_team_member(client_obj.id, team_member_data, admin_user.id)

    # Verify password is not plaintext placeholder
    assert invited_user.hashed_password != "PENDING_USER_NO_PASSWORD"
    # Verify password is hashed (bcrypt starts with $2b$)
    assert invited_user.hashed_password.startswith("$2b$")
    # Verify password cannot be verified with any common string
    assert not security.verify_password("password", invited_user.hashed_password)
    assert not security.verify_password("PENDING", invited_user.hashed_password)


@pytest.mark.asyncio
async def test_p22_pending_user_cannot_login_before_activation(client: AsyncClient, db_session: AsyncSession):
    """P2-2: PENDING users should not be able to login (activation required)"""
    # Create client first
    client_obj = Client(
        id=str(uuid.uuid4()),
        company_name=f"TestCorp-{uuid.uuid4()}",
        subscription_plan="GRATUIT",
        subscription_status="ACTIVE",
        minutes_included=600
    )
    db_session.add(client_obj)
    await db_session.flush()

    # Create PENDING user
    pending_user = User(
        id=str(uuid.uuid4()),
        client_id=client_obj.id,
        email=f"pending_{uuid.uuid4()}@example.com",
        full_name="Pending User",
        hashed_password=security.get_password_hash("Password123!"),
        status=UserStatus.PENDING.value  # ← PENDING, not ACTIVE
    )
    db_session.add(pending_user)
    await db_session.commit()

    # Try to login
    response = await client.post(
        "/api/v1/auth/login",
        data={
            "username": pending_user.email,
            "password": "Password123!"
        }
    )
    assert response.status_code == 400
    assert "Inactive" in response.json()["detail"]


@pytest.mark.asyncio
async def test_p23_non_creator_cannot_update_meeting(db_session: AsyncSession):
    """P2-3: Non-creator user should not be able to cancel meeting"""
    # Create client
    client_id = str(uuid.uuid4())
    client_obj = Client(
        id=client_id,
        company_name=f"TestCorp-{uuid.uuid4()}",
        subscription_plan="GRATUIT",
        subscription_status="ACTIVE",
        minutes_included=600
    )
    db_session.add(client_obj)
    await db_session.flush()

    # Create creator user
    creator = User(
        id=str(uuid.uuid4()),
        client_id=client_id,
        email=f"creator_{uuid.uuid4()}@example.com",
        full_name="Creator",
        hashed_password=security.get_password_hash("Pass123!"),
        status=UserStatus.ACTIVE.value
    )
    db_session.add(creator)
    await db_session.flush()

    # Create non-creator user
    other_user = User(
        id=str(uuid.uuid4()),
        client_id=client_id,
        email=f"other_{uuid.uuid4()}@example.com",
        full_name="Other User",
        hashed_password=security.get_password_hash("Pass123!"),
        status=UserStatus.ACTIVE.value
    )
    db_session.add(other_user)
    await db_session.commit()

    # Create meeting as creator
    meeting = Meeting(
        id=str(uuid.uuid4()),
        client_id=client_id,
        title="Test Meeting",
        description="Test Description",
        start_time=datetime.now(timezone.utc) + timedelta(hours=1),
        end_time=datetime.now(timezone.utc) + timedelta(hours=2),
        creator_id=creator.id,
        status="planned"
    )
    db_session.add(meeting)
    await db_session.commit()

    # Try to update meeting as non-creator via MeetingService
    meeting_service = MeetingService(db_session)
    from fastapi import HTTPException

    update_data = MeetingUpdate(status="cancelled")
    
    # Should raise HTTPException with 403
    with pytest.raises(HTTPException) as exc_info:
        await meeting_service.update_meeting(
            meeting.id, 
            client_id, 
            update_data, 
            current_user_id=other_user.id
        )
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_p23_creator_can_update_meeting(db_session: AsyncSession):
    """P2-3: Meeting creator should be able to cancel meeting"""
    # Create client
    client_id = str(uuid.uuid4())
    client_obj = Client(
        id=client_id,
        company_name=f"TestCorp-{uuid.uuid4()}",
        subscription_plan="GRATUIT",
        subscription_status="ACTIVE",
        minutes_included=600
    )
    db_session.add(client_obj)
    await db_session.flush()

    # Create creator user
    creator = User(
        id=str(uuid.uuid4()),
        client_id=client_id,
        email=f"creator_{uuid.uuid4()}@example.com",
        full_name="Creator",
        hashed_password=security.get_password_hash("Pass123!"),
        status=UserStatus.ACTIVE.value
    )
    db_session.add(creator)
    await db_session.commit()

    # Create meeting as creator
    meeting = Meeting(
        id=str(uuid.uuid4()),
        client_id=client_id,
        title="Test Meeting",
        description="Test Description",
        start_time=datetime.now(timezone.utc) + timedelta(hours=1),
        end_time=datetime.now(timezone.utc) + timedelta(hours=2),
        creator_id=creator.id,
        status="planned"
    )
    db_session.add(meeting)
    await db_session.commit()

    # Update meeting as creator
    meeting_service = MeetingService(db_session)

    update_data = MeetingUpdate(status="cancelled")
    updated_meeting = await meeting_service.update_meeting(
        meeting.id, 
        client_id, 
        update_data, 
        current_user_id=creator.id  # ← Creator updating their own meeting
    )
    
    assert updated_meeting is not None
    assert updated_meeting.status == "cancelled"


@pytest.mark.asyncio
async def test_p23_admin_can_update_any_meeting(db_session: AsyncSession):
    """P2-3: Admin user should be able to cancel any meeting"""
    # Create client
    client_id = str(uuid.uuid4())
    client_obj = Client(
        id=client_id,
        company_name=f"TestCorp-{uuid.uuid4()}",
        subscription_plan="GRATUIT",
        subscription_status="ACTIVE",
        minutes_included=600
    )
    db_session.add(client_obj)
    await db_session.flush()

    # Load admin role
    role_stmt = select(Role).where(Role.name == "admin")
    role_res = await db_session.execute(role_stmt)
    admin_role = role_res.scalar_one()

    # Create admin user with role assigned at creation
    admin = User(
        id=str(uuid.uuid4()),
        client_id=client_id,
        email=f"admin_{uuid.uuid4()}@example.com",
        full_name="Admin",
        hashed_password=security.get_password_hash("Pass123!"),
        status=UserStatus.ACTIVE.value,
        roles=[admin_role],
    )
    db_session.add(admin)
    await db_session.flush()

    # Create creator user
    creator = User(
        id=str(uuid.uuid4()),
        client_id=client_id,
        email=f"creator_{uuid.uuid4()}@example.com",
        full_name="Creator",
        hashed_password=security.get_password_hash("Pass123!"),
        status=UserStatus.ACTIVE.value
    )
    db_session.add(creator)
    await db_session.commit()

    # Create meeting as creator
    meeting = Meeting(
        id=str(uuid.uuid4()),
        client_id=client_id,
        title="Test Meeting",
        description="Test Description",
        start_time=datetime.now(timezone.utc) + timedelta(hours=1),
        end_time=datetime.now(timezone.utc) + timedelta(hours=2),
        creator_id=creator.id,
        status="planned"
    )
    db_session.add(meeting)
    await db_session.commit()

    # Update meeting as admin (not creator)
    meeting_service = MeetingService(db_session)

    update_data = MeetingUpdate(status="cancelled")
    updated_meeting = await meeting_service.update_meeting(
        meeting.id, 
        client_id, 
        update_data, 
        current_user_id=admin.id  # ← Admin updating others' meeting
    )
    
    assert updated_meeting is not None
    assert updated_meeting.status == "cancelled"


@pytest.mark.asyncio
async def test_p24_meeting_end_time_must_be_after_start_time(db_session: AsyncSession):
    """P2-4: Database should enforce end_time > start_time via CHECK constraint"""
    # Create client and user
    client_id = str(uuid.uuid4())
    client_obj = Client(
        id=client_id,
        company_name=f"TestCorp-{uuid.uuid4()}",
        subscription_plan="GRATUIT",
        subscription_status="ACTIVE",
        minutes_included=600
    )
    db_session.add(client_obj)

    creator = User(
        id=str(uuid.uuid4()),
        client_id=client_id,
        email=f"creator_{uuid.uuid4()}@example.com",
        full_name="Creator",
        hashed_password=security.get_password_hash("Pass123!"),
        status=UserStatus.ACTIVE.value
    )
    db_session.add(creator)
    await db_session.flush()

    now = datetime.now(timezone.utc)
    
    # Try to create meeting with end_time before start_time
    invalid_meeting = Meeting(
        id=str(uuid.uuid4()),
        client_id=client_id,
        title="Invalid Meeting",
        start_time=now + timedelta(hours=2),
        end_time=now + timedelta(hours=1),  # ← end_time BEFORE start_time
        creator_id=creator.id,
        status="planned"
    )
    db_session.add(invalid_meeting)
    
    # Should fail at commit due to CHECK constraint
    from sqlalchemy.exc import IntegrityError
    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.mark.asyncio
async def test_p24_meeting_with_null_end_time_is_allowed(db_session: AsyncSession):
    """P2-4: Meeting with NULL end_time should be allowed"""
    # Create client and user
    client_id = str(uuid.uuid4())
    client_obj = Client(
        id=client_id,
        company_name=f"TestCorp-{uuid.uuid4()}",
        subscription_plan="GRATUIT",
        subscription_status="ACTIVE",
        minutes_included=600
    )
    db_session.add(client_obj)

    creator = User(
        id=str(uuid.uuid4()),
        client_id=client_id,
        email=f"creator_{uuid.uuid4()}@example.com",
        full_name="Creator",
        hashed_password=security.get_password_hash("Pass123!"),
        status=UserStatus.ACTIVE.value
    )
    db_session.add(creator)
    await db_session.flush()

    now = datetime.now(timezone.utc)
    
    # Create meeting with NULL end_time
    meeting = Meeting(
        id=str(uuid.uuid4()),
        client_id=client_id,
        title="Open-ended Meeting",
        start_time=now + timedelta(hours=1),
        end_time=None,  # ← NULL end_time
        creator_id=creator.id,
        status="planned"
    )
    db_session.add(meeting)
    await db_session.commit()
    
    # Verify meeting was created
    stmt = select(Meeting).where(Meeting.id == meeting.id)
    res = await db_session.execute(stmt)
    saved = res.scalar_one()
    assert saved.end_time is None


@pytest.mark.asyncio
async def test_p25_duplicate_participant_email_rejected(db_session: AsyncSession):
    """P2-5: Unique constraint on (meeting_id, email) should prevent duplicates"""
    # Create meeting
    client_id = str(uuid.uuid4())
    client_obj = Client(
        id=client_id,
        company_name=f"TestCorp-{uuid.uuid4()}",
        subscription_plan="GRATUIT",
        subscription_status="ACTIVE",
        minutes_included=600
    )
    db_session.add(client_obj)

    creator = User(
        id=str(uuid.uuid4()),
        client_id=client_id,
        email=f"creator_{uuid.uuid4()}@example.com",
        full_name="Creator",
        hashed_password=security.get_password_hash("Pass123!"),
        status=UserStatus.ACTIVE.value
    )
    db_session.add(creator)
    await db_session.flush()

    meeting = Meeting(
        id=str(uuid.uuid4()),
        client_id=client_id,
        title="Test Meeting",
        start_time=datetime.now(timezone.utc) + timedelta(hours=1),
        end_time=datetime.now(timezone.utc) + timedelta(hours=2),
        creator_id=creator.id,
        status="planned"
    )
    db_session.add(meeting)
    await db_session.flush()

    # Add first participant
    p1 = Participant(
        id=str(uuid.uuid4()),
        meeting_id=meeting.id,
        email=f"participant_{uuid.uuid4()}@example.com",
        name="Participant 1"
    )
    db_session.add(p1)
    await db_session.flush()

    # Try to add duplicate participant with same email
    p2 = Participant(
        id=str(uuid.uuid4()),
        meeting_id=meeting.id,
        email=p1.email,  # ← Same email
        name="Participant 2"
    )
    db_session.add(p2)
    
    # Should fail due to UNIQUE constraint
    from sqlalchemy.exc import IntegrityError
    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.mark.asyncio
async def test_p25_same_email_different_meetings_allowed(db_session: AsyncSession):
    """P2-5: Same email in different meetings should be allowed"""
    # Create client and user
    client_id = str(uuid.uuid4())
    client_obj = Client(
        id=client_id,
        company_name=f"TestCorp-{uuid.uuid4()}",
        subscription_plan="GRATUIT",
        subscription_status="ACTIVE",
        minutes_included=600
    )
    db_session.add(client_obj)

    creator = User(
        id=str(uuid.uuid4()),
        client_id=client_id,
        email=f"creator_{uuid.uuid4()}@example.com",
        full_name="Creator",
        hashed_password=security.get_password_hash("Pass123!"),
        status=UserStatus.ACTIVE.value
    )
    db_session.add(creator)
    await db_session.flush()

    # Create two meetings
    meeting1 = Meeting(
        id=str(uuid.uuid4()),
        client_id=client_id,
        title="Meeting 1",
        start_time=datetime.now(timezone.utc) + timedelta(hours=1),
        end_time=datetime.now(timezone.utc) + timedelta(hours=2),
        creator_id=creator.id,
        status="planned"
    )
    meeting2 = Meeting(
        id=str(uuid.uuid4()),
        client_id=client_id,
        title="Meeting 2",
        start_time=datetime.now(timezone.utc) + timedelta(hours=3),
        end_time=datetime.now(timezone.utc) + timedelta(hours=4),
        creator_id=creator.id,
        status="planned"
    )
    db_session.add_all([meeting1, meeting2])
    await db_session.flush()

    # Add same email to both meetings
    shared_email = f"shared_{uuid.uuid4()}@example.com"
    p1 = Participant(
        id=str(uuid.uuid4()),
        meeting_id=meeting1.id,
        email=shared_email,
        name="Shared Participant"
    )
    p2 = Participant(
        id=str(uuid.uuid4()),
        meeting_id=meeting2.id,
        email=shared_email,  # ← Same email, different meeting
        name="Shared Participant"
    )
    db_session.add_all([p1, p2])
    await db_session.commit()  # ← Should succeed

    # Verify both were added
    stmt = select(Participant).where(Participant.email == shared_email)
    res = await db_session.execute(stmt)
    participants = res.scalars().all()
    assert len(participants) == 2
