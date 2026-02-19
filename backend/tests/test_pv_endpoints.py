import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.models.user import User, UserRole
from backend.app.models.meeting import Meeting, MeetingStatus
from backend.app.models.transcription import Transcription
from backend.app.models.pv import PV, PVStatus
from backend.app.schemas.pv import PVGenerate, PVUpdate, PVValidate
from sqlalchemy import select
from backend.app.core.security import create_access_token, get_password_hash, create_access_token_for_user
from backend.app.core.config import settings
from datetime import datetime, timedelta
import json
from unittest.mock import AsyncMock, patch

# Helper function to create a user with a specific role
async def create_test_user(db_session: AsyncSession, username: str, email: str, role: UserRole):
    password = "pw".encode("utf-8")
    hashed_password = get_password_hash(password)
    user = User(
        username=username,
        email=email,
        hashed_password=hashed_password,
        full_name=f"{username} Full Name",
        role=role,
        is_active=True,
        is_superuser=False
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user

# Helper function to get a token for a user
async def get_user_token(user: User):
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return create_access_token_for_user(
        user_id=user.id, expires_delta=access_token_expires
    )

# Helper function to create a meeting
async def create_test_meeting(db_session: AsyncSession, organizer: User):
    await db_session.refresh(organizer)
    meeting = Meeting(
        title="Test Meeting",
        description="Description for test meeting",
        date=datetime.now().date(),
        duration=60,
        location="Online",
        organizer_id=organizer.id,
        status=MeetingStatus.PLANNED
    )
    db_session.add(meeting)
    await db_session.flush()
    await db_session.refresh(meeting)
    return meeting

# Helper function to create a transcription
async def create_test_transcription(db_session: AsyncSession, meeting_id: int):
    transcription = Transcription(
        meeting_id=meeting_id,
        recording_id=1,
        content="The team decided to proceed with Project X. We also agreed to postpone the marketing campaign.",
        language="en",
        status="COMPLETED"
    )
    db_session.add(transcription)
    await db_session.flush()
    await db_session.refresh(transcription)
    return transcription

# Helper function to create a PV
async def create_test_pv(db_session: AsyncSession, meeting: Meeting, generator: User, content: str = "Mock PV Content", validator: User = None):
    if meeting not in db_session:
        db_session.add(meeting)
    if generator not in db_session:
        db_session.add(generator)
    if validator and validator not in db_session:
        db_session.add(validator)

    await db_session.refresh(meeting)
    await db_session.refresh(generator)
    if validator:
        await db_session.refresh(validator)
    
    pv = PV(
        meeting_id=meeting.id,
        generated_by_id=generator.id,
        content=content,
        summary="Mock Summary",
        decisions=["Decision 1"],
        status=PVStatus.DRAFT,
    )
    if validator:
        pv.validated_by_id = validator.id
        pv.validated_at = datetime.now()
    db_session.add(pv)
    await db_session.flush()
    await db_session.refresh(pv)
    return pv

@pytest.mark.asyncio
async def test_generate_pv(client: AsyncClient, db_session: AsyncSession):
    user = await create_test_user(db_session, "testuser", "test@example.com", UserRole.PARTICIPANT)
    token = await get_user_token(user)
    meeting = await create_test_meeting(db_session, user)
    transcription = await create_test_transcription(db_session, meeting.id)
    transcription_content = transcription.content  # Load content before session closes

    pv_generate_data = PVGenerate(transcription_id=transcription.id, template="default")
    response = await client.post(
        f"/api/v1/pv/{meeting.id}/generate",
        json=pv_generate_data.dict(),
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    pv_data = response.json()
    assert "id" in pv_data
    assert pv_data["meeting_id"] == meeting.id
    assert "content" in pv_data

@pytest.mark.asyncio
@patch("backend.app.services.pv_service.mistral_client.generate_pv", new_callable=AsyncMock)
async def test_generate_pv_with_mock(mock_generate_pv, client: AsyncClient, db_session: AsyncSession):
    mock_generate_pv.return_value = "This is a mocked PV content."
    
    user = await create_test_user(db_session, "mockuser", "mock@example.com", UserRole.PARTICIPANT)
    token = await get_user_token(user)
    meeting = await create_test_meeting(db_session, user)
    transcription = await create_test_transcription(db_session, meeting.id)
    transcription_content = transcription.content  # Load content before session closes

    pv_generate_data = PVGenerate(transcription_id=transcription.id, template="default")
    response = await client.post(
        f"/api/v1/pv/{meeting.id}/generate",
        json=pv_generate_data.dict(),
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    pv_data = response.json()
    assert pv_data["content"] == "This is a mocked PV content."
    mock_generate_pv.assert_called_once_with(transcription_content)

@pytest.mark.asyncio
async def test_validate_pv_as_dg(client: AsyncClient, db_session: AsyncSession):
    dg_user = await create_test_user(db_session, "dguser", "dg@example.com", UserRole.DG)
    normal_user = await create_test_user(db_session, "normaluser", "normal@example.com", UserRole.PARTICIPANT)
    
    dg_token = await get_user_token(dg_user)

    meeting = await create_test_meeting(db_session, normal_user)
    pv = await create_test_pv(db_session, meeting, normal_user, validator=dg_user)

    pv_validate_data = PVValidate(comment="Looks good!")
    response = await client.post(
        f"/api/v1/pv/{pv.id}/validate",
        json=pv_validate_data.model_dump(),
        headers={"Authorization": f"Bearer {dg_token}"}
    )
    assert response.status_code == 200
    validated_pv = response.json()
    assert validated_pv["validated_by_id"] == dg_user.id
    assert validated_pv["validation_comment"] == "Looks good!"
    assert validated_pv["validated_at"] is not None
    assert validated_pv["is_validated"] is True

@pytest.mark.asyncio
async def test_validate_pv_as_normal_user_403(client: AsyncClient, db_session: AsyncSession):
    normal_user = await create_test_user(db_session, "normaluser2", "normal2@example.com", UserRole.PARTICIPANT)
    admin_user = await create_test_user(db_session, "adminuser", "admin@example.com", UserRole.ADMIN)
    
    normal_token = await get_user_token(normal_user)

    meeting = await create_test_meeting(db_session, admin_user)
    pv = await create_test_pv(db_session, meeting, admin_user)

    pv_validate_data = PVValidate(comment="I want to validate!")
    response = await client.post(
        f"/api/v1/pv/{pv.id}/validate",
        json=pv_validate_data.dict(),
        headers={"Authorization": f"Bearer {normal_token}"}
    )
    assert response.status_code == 403
    assert "Only DGs can validate PVs" in response.json()["detail"]

@pytest.mark.asyncio
async def test_extract_decisions_from_pv(client: AsyncClient, db_session: AsyncSession):
    user = await create_test_user(db_session, "user_decisions", "decisions@example.com", UserRole.PARTICIPANT)
    token = await get_user_token(user)
    meeting = await create_test_meeting(db_session, user)
    pv_content = "During the meeting, it was decided that Project Alpha will be launched next month. We also agreed to allocate more budget to marketing."
    pv = await create_test_pv(db_session, meeting, user, content=pv_content)
    pv_id = pv.id

    response = await client.post(
        f"/api/v1/pv/{pv_id}/extract-decisions",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    result = response.json()
    assert "pv_id" in result
    assert "decisions" in result
    assert isinstance(result["decisions"], list)
    assert len(result["decisions"]) > 0
    updated_pv_response = await client.get(
        f"/api/v1/pv/{pv_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert updated_pv_response.status_code == 200
    updated_pv_data = updated_pv_response.json()
    assert updated_pv_data["decisions"] == result["decisions"]

@pytest.mark.asyncio
async def test_generate_pv_pdf(client: AsyncClient, db_session: AsyncSession):
    user = await create_test_user(db_session, "user_pdf", "pdf@example.com", UserRole.PARTICIPANT)
    token = await get_user_token(user)
    meeting = await create_test_meeting(db_session, user)
    pv = await create_test_pv(db_session, meeting, user)

    response = await client.get(
        f"/api/v1/pv/{pv.id}/export/pdf",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"] == f"attachment; filename=pv_{pv.id}.pdf"
    assert len(response.content) > 0

@pytest.mark.asyncio
async def test_generate_pv_docx(client: AsyncClient, db_session: AsyncSession):
    user = await create_test_user(db_session, "user_docx", "docx@example.com", UserRole.PARTICIPANT)
    token = await get_user_token(user)
    meeting = await create_test_meeting(db_session, user)
    pv = await create_test_pv(db_session, meeting, user)

    response = await client.get(
        f"/api/v1/pv/{pv.id}/export/docx",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    assert response.headers["content-disposition"] == f"attachment; filename=pv_{pv.id}.docx"
    assert len(response.content) > 0


@pytest.mark.asyncio
async def test_extract_action_points_from_pv(client: AsyncClient, db_session: AsyncSession):
    user = await create_test_user(db_session, "user_actions", "actions@example.com", UserRole.PARTICIPANT)
    token = await get_user_token(user)
    meeting = await create_test_meeting(db_session, user)
    pv_content = "Action point: Prepare the project plan, assigned to Test User, deadline 2026-02-20. Another action: Follow up with the marketing team."
    pv = await create_test_pv(db_session, meeting, user, content=pv_content)
    pv_id = pv.id

    response = await client.post(
        f"/api/v1/pv/{pv_id}/extract-action-points",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    result = response.json()
    assert "pv_id" in result
    assert "action_points" in result
    assert isinstance(result["action_points"], list)
    assert len(result["action_points"]) > 0
    updated_pv_response = await client.get(
        f"/api/v1/pv/{pv_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert updated_pv_response.status_code == 200
    updated_pv_data = updated_pv_response.json()
    assert updated_pv_data["action_points"] == result["action_points"]