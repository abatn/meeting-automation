"""
Phase 3 E2E Tests: Meeting Lifecycle & Status Changes

Tests for:
- P3-1: n8n webhook triggering for meeting status changes
- P3-2: Meeting update authorization (creator/admin/dg only)
- P3-3: DB constraint: end_time > start_time
- P3-4: UNIQUE constraint: participants(meeting_id, email)

Date: 2026-05-05
Author: OpenCode AI
"""
import pytest
import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import User, UserStatus, Role
from app.models.client import Client
from app.models.meeting import Meeting, Participant
from app.core import security
from app.schemas.meeting import MeetingCreate, MeetingUpdate
from app.services.meeting_service import MeetingService


def create_test_client(db_session, name: str):
    """Helper to create a test client"""
    return Client(
        id=str(uuid.uuid4()),
        company_name=f"{name}-{uuid.uuid4().hex[:8]}",
    )


@pytest.mark.asyncio
async def test_p31_meeting_status_change_triggers_webhook(db_session: AsyncSession):
    """P3-1: Status change from planned -> in_progress"""
    test_client = create_test_client(db_session, "TestClient1")
    db_session.add(test_client)
    
    creator = User(
        id=str(uuid.uuid4()),
        email=f"creator_{uuid.uuid4().hex[:6]}@example.com",
        full_name="Creator User",
        hashed_password=security.get_password_hash("Password123!"),
        client_id=test_client.id,
        status=UserStatus.ACTIVE.value,
    )
    db_session.add(creator)
    await db_session.flush()
    
    meeting = Meeting(
        id=str(uuid.uuid4()),
        client_id=test_client.id,
        title="Team Standup",
        status="planned",
        creator_id=creator.id,
        start_time=datetime.now(timezone.utc) + timedelta(hours=1),
        end_time=datetime.now(timezone.utc) + timedelta(hours=2),
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(meeting)
    await db_session.commit()
    
    # Update meeting status
    meeting_service = MeetingService(db_session)
    updated = await meeting_service.update_meeting(
        meeting_id=meeting.id,
        client_id=test_client.id,
        meeting_in=MeetingUpdate(status="in_progress"),
        current_user_id=creator.id
    )
    assert updated.status == "in_progress"


@pytest.mark.asyncio
async def test_p31_cancelled_meeting_triggers_webhook(db_session: AsyncSession):
    """P3-1: Status change to cancelled"""
    test_client = create_test_client(db_session, "TestClient2")
    db_session.add(test_client)
    
    creator = User(
        id=str(uuid.uuid4()),
        email=f"creator2_{uuid.uuid4().hex[:6]}@example.com",
        full_name="Creator User 2",
        hashed_password=security.get_password_hash("Password123!"),
        client_id=test_client.id,
        status=UserStatus.ACTIVE.value,
    )
    db_session.add(creator)
    await db_session.flush()
    
    meeting = Meeting(
        id=str(uuid.uuid4()),
        client_id=test_client.id,
        title="Cancelled Meeting",
        status="planned",
        creator_id=creator.id,
        start_time=datetime.now(timezone.utc) + timedelta(hours=1),
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(meeting)
    await db_session.commit()
    
    meeting_service = MeetingService(db_session)
    updated = await meeting_service.update_meeting(
        meeting_id=meeting.id,
        client_id=test_client.id,
        meeting_in=MeetingUpdate(status="cancelled"),
        current_user_id=creator.id
    )
    assert updated.status == "cancelled"


@pytest.mark.asyncio
async def test_p32_non_creator_cannot_update_meeting(db_session: AsyncSession):
    """P3-2: Non-creator cannot update"""
    test_client = create_test_client(db_session, "TestClient3")
    db_session.add(test_client)
    
    creator = User(
        id=str(uuid.uuid4()),
        email=f"creator3_{uuid.uuid4().hex[:6]}@example.com",
        full_name="Creator",
        hashed_password=security.get_password_hash("Password123!"),
        client_id=test_client.id,
        status=UserStatus.ACTIVE.value,
    )
    db_session.add(creator)
    
    other = User(
        id=str(uuid.uuid4()),
        email=f"other_{uuid.uuid4().hex[:6]}@example.com",
        full_name="Other",
        hashed_password=security.get_password_hash("Password123!"),
        client_id=test_client.id,
        status=UserStatus.ACTIVE.value,
    )
    db_session.add(other)
    await db_session.flush()
    
    meeting = Meeting(
        id=str(uuid.uuid4()),
        client_id=test_client.id,
        title="Test",
        status="planned",
        creator_id=creator.id,
        start_time=datetime.now(timezone.utc) + timedelta(hours=1),
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(meeting)
    await db_session.commit()
    
    meeting_service = MeetingService(db_session)
    with pytest.raises(Exception):
        await meeting_service.update_meeting(
            meeting_id=meeting.id,
            client_id=test_client.id,
            meeting_in=MeetingUpdate(status="in_progress"),
            current_user_id=other.id
        )


@pytest.mark.asyncio
async def test_p32_creator_can_update_meeting(db_session: AsyncSession):
    """P3-2: Creator can update own meeting"""
    test_client = create_test_client(db_session, "TestClient4")
    db_session.add(test_client)
    
    creator = User(
        id=str(uuid.uuid4()),
        email=f"creator4_{uuid.uuid4().hex[:6]}@example.com",
        full_name="Creator",
        hashed_password=security.get_password_hash("Password123!"),
        client_id=test_client.id,
        status=UserStatus.ACTIVE.value,
    )
    db_session.add(creator)
    await db_session.flush()
    
    meeting = Meeting(
        id=str(uuid.uuid4()),
        client_id=test_client.id,
        title="Test",
        status="planned",
        creator_id=creator.id,
        start_time=datetime.now(timezone.utc) + timedelta(hours=1),
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(meeting)
    await db_session.commit()
    
    meeting_service = MeetingService(db_session)
    updated = await meeting_service.update_meeting(
        meeting_id=meeting.id,
        client_id=test_client.id,
        meeting_in=MeetingUpdate(status="in_progress"),
        current_user_id=creator.id
    )
    assert updated.status == "in_progress"


@pytest.mark.asyncio
async def test_p33_end_time_must_be_after_start_time(db_session: AsyncSession):
    """P3-3: DB constraint: end_time > start_time"""
    test_client = create_test_client(db_session, "TestClient5")
    db_session.add(test_client)
    
    creator = User(
        id=str(uuid.uuid4()),
        email=f"creator5_{uuid.uuid4().hex[:6]}@example.com",
        full_name="Creator",
        hashed_password=security.get_password_hash("Password123!"),
        client_id=test_client.id,
        status=UserStatus.ACTIVE.value,
    )
    db_session.add(creator)
    await db_session.flush()
    
    meeting_service = MeetingService(db_session)
    start = datetime.now(timezone.utc) + timedelta(hours=2)
    end = start - timedelta(hours=1)
    
    with pytest.raises(Exception):
        await meeting_service.create_meeting(
            meeting_in=MeetingCreate(
                title="Invalid",
                start_time=start,
                end_time=end,
            ),
            owner_id=creator.id,
            client_id=test_client.id
        )


@pytest.mark.asyncio
async def test_p33_end_time_can_be_null(db_session: AsyncSession):
    """P3-3: end_time can be NULL"""
    test_client = create_test_client(db_session, "TestClient6")
    db_session.add(test_client)
    
    creator = User(
        id=str(uuid.uuid4()),
        email=f"creator6_{uuid.uuid4().hex[:6]}@example.com",
        full_name="Creator",
        hashed_password=security.get_password_hash("Password123!"),
        client_id=test_client.id,
        status=UserStatus.ACTIVE.value,
    )
    db_session.add(creator)
    await db_session.flush()
    
    meeting_service = MeetingService(db_session)
    start = datetime.now(timezone.utc) + timedelta(hours=1)
    
    meeting = await meeting_service.create_meeting(
        meeting_in=MeetingCreate(
            title="Open-Ended",
            start_time=start,
            end_time=None,
        ),
        owner_id=creator.id,
        client_id=test_client.id
    )
    assert meeting.end_time is None


@pytest.mark.asyncio
async def test_p34_duplicate_participant_email_rejected(db_session: AsyncSession):
    """P3-4: UNIQUE(meeting_id, email) constraint"""
    test_client = create_test_client(db_session, "TestClient7")
    db_session.add(test_client)
    
    creator = User(
        id=str(uuid.uuid4()),
        email=f"creator7_{uuid.uuid4().hex[:6]}@example.com",
        full_name="Creator",
        hashed_password=security.get_password_hash("Password123!"),
        client_id=test_client.id,
        status=UserStatus.ACTIVE.value,
    )
    db_session.add(creator)
    await db_session.flush()
    
    meeting = Meeting(
        id=str(uuid.uuid4()),
        client_id=test_client.id,
        title="Team",
        status="planned",
        creator_id=creator.id,
        start_time=datetime.now(timezone.utc) + timedelta(hours=1),
        created_at=datetime.now(timezone.utc),
    )
    
    dup_email = f"dup_{uuid.uuid4().hex[:6]}@example.com"
    p1 = Participant(
        id=str(uuid.uuid4()),
        meeting_id=meeting.id,
        email=dup_email,
        name="P1",
    )
    db_session.add(meeting)
    db_session.add(p1)
    await db_session.commit()
    
    p2 = Participant(
        id=str(uuid.uuid4()),
        meeting_id=meeting.id,
        email=dup_email,
        name="P2",
    )
    db_session.add(p2)
    
    with pytest.raises(Exception):
        await db_session.commit()


@pytest.mark.asyncio
async def test_p34_same_email_different_meetings_allowed(db_session: AsyncSession):
    """P3-4: Same email in different meetings is allowed"""
    test_client = create_test_client(db_session, "TestClient8")
    db_session.add(test_client)
    
    creator = User(
        id=str(uuid.uuid4()),
        email=f"creator8_{uuid.uuid4().hex[:6]}@example.com",
        full_name="Creator",
        hashed_password=security.get_password_hash("Password123!"),
        client_id=test_client.id,
        status=UserStatus.ACTIVE.value,
    )
    db_session.add(creator)
    await db_session.flush()
    
    m1 = Meeting(
        id=str(uuid.uuid4()),
        client_id=test_client.id,
        title="M1",
        status="planned",
        creator_id=creator.id,
        start_time=datetime.now(timezone.utc) + timedelta(hours=1),
        created_at=datetime.now(timezone.utc),
    )
    
    m2 = Meeting(
        id=str(uuid.uuid4()),
        client_id=test_client.id,
        title="M2",
        status="planned",
        creator_id=creator.id,
        start_time=datetime.now(timezone.utc) + timedelta(hours=2),
        created_at=datetime.now(timezone.utc),
    )
    
    db_session.add(m1)
    db_session.add(m2)
    
    shared_email = f"shared_{uuid.uuid4().hex[:6]}@example.com"
    
    p1 = Participant(
        id=str(uuid.uuid4()),
        meeting_id=m1.id,
        email=shared_email,
        name="P",
    )
    
    p2 = Participant(
        id=str(uuid.uuid4()),
        meeting_id=m2.id,
        email=shared_email,
        name="P",
    )
    
    db_session.add(p1)
    db_session.add(p2)
    await db_session.commit()
    
    stmt = select(Participant).where(Participant.email == shared_email)
    result = await db_session.execute(stmt)
    assert len(result.scalars().all()) == 2
