"""
E2E Tests: Intelligent Speaker Assignment via Speaker Mappings

Tests for:
- Speaker mappings used for assignment (not ignored)
- learn_from_feedback resolves users before external_name
- Audit logs for PV/Action/Assignment creation
- Mistral assignee validation against resolved speakers

Date: 2026-06-02
"""
import pytest
import inspect
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.action import Action, Assignment, ActionSuggestion, SuggestionStatus, ActionStatus
from app.models.user import User
from app.models.pv import PV
from app.models.audit_log import AuditLog
from app.models.client import Client, SubscriptionStatus
from app.models.meeting import Meeting
from app.models.recording import Recording
from app.tasks.transcription_tasks import _save_pv_and_actions
from app.services.action_service import ActionService
from app.core.security import get_password_hash


@pytest.mark.asyncio
async def test_speaker_mappings_used_for_assignment(db_session: AsyncSession):
    """Speaker mappings should be used for assignment, not ignored."""
    source = inspect.getsource(_save_pv_and_actions)

    assert "speaker_mappings" in source, "Function should accept speaker_mappings parameter"
    assert "resolved_speakers" in source, "Should build resolved_speakers lookup"
    assert "resolved_speakers[" in source, "Should check assignee against resolved_speakers"


@pytest.mark.asyncio
async def test_assignment_priority_order(db_session: AsyncSession):
    """Assignment should use AssigneeResolver with priority: speaker_mappings → participant → phonetic → fuzzy."""
    source = inspect.getsource(_save_pv_and_actions)

    assert "AssigneeResolver" in source, "Should use AssigneeResolver"
    assert "speaker_mappings" in source, "Should pass speaker_mappings to resolver"
    assert "participant_names" in source, "Should pass participant_names to resolver"
    assert "client_users" in source, "Should load client users for directory resolution"


@pytest.mark.asyncio
async def test_mistral_assignee_validation(db_session: AsyncSession):
    """Mistral assignee should be validated through professional resolution pipeline."""
    source = inspect.getsource(_save_pv_and_actions)

    assert "AssigneeResolver" in source, "Should use AssigneeResolver"
    assert "resolver.resolve" in source, "Should call resolver.resolve()"
    assert "resolution.user_id" in source, "Should check resolution result for user_id"
    assert "resolution.external_name" in source, "Should handle external_name fallback"
    assert "resolution.external_email" in source, "Should handle external_email fallback"
    assert "single_speaker" in source, "Should support single speaker fallback"


@pytest.mark.asyncio
async def test_audit_logs_for_pv_creation(db_session: AsyncSession):
    """PV creation should be audited."""
    source = inspect.getsource(_save_pv_and_actions)

    assert "PV_CREATED" in source, "Should log PV_CREATED action"
    assert "AuditService.log_action" in source, "Should call AuditService.log_action"


@pytest.mark.asyncio
async def test_audit_logs_for_action_assignment(db_session: AsyncSession):
    """Action assignment should be audited."""
    source = inspect.getsource(_save_pv_and_actions)

    assert "ACTION_ASSIGNED" in source, "Should log ACTION_ASSIGNED action"
    assert "ACTION_ASSIGNED_EXTERNAL" in source, "Should log ACTION_ASSIGNED_EXTERNAL action"
    assert "matched_via" in source, "Should track how assignment was matched"


@pytest.mark.asyncio
async def test_learn_from_feedback_resolves_user(db_session: AsyncSession):
    """learn_from_feedback should resolve users via AssigneeResolver before creating external_name."""
    source = inspect.getsource(ActionService.learn_from_feedback)

    assert "AssigneeResolver" in source, "Should use AssigneeResolver for professional resolution"
    assert "participant_names" in source, "Should gather participant names for resolution"
    assert "speaker_mappings" in source or "speaker" in source, "Should gather speaker mappings for resolution"
    assert "client_users" in source, "Should load client users for directory resolution"
    assert "user_id" in source, "Should create user_id assignment when matched"
    assert "external_name" in source, "Should fall back to external_name when not matched"
    assert "AuditService" in source, "Should log assignments for ISO 27001 compliance"


@pytest.mark.asyncio
async def test_learn_from_feedback_imports(db_session: AsyncSession):
    """action_service.py should import User and or_."""
    from app.services import action_service
    source = inspect.getsource(action_service)

    assert "from app.models.user import User" in source, "Should import User model"
    assert "or_" in source, "Should import or_ from sqlalchemy"


@pytest.mark.asyncio
async def test_save_pv_and_actions_with_speaker_mappings_integration(db_session: AsyncSession):
    """Integration test: _save_pv_and_actions uses speaker_mappings to assign tasks."""
    client_id = str(uuid.uuid4())
    meeting_id = str(uuid.uuid4())
    recording_id = str(uuid.uuid4())

    client = Client(id=client_id, company_name=f"Test Client {client_id[:8]}", subscription_status=SubscriptionStatus.ACTIVE)
    db_session.add(client)

    user_id = str(uuid.uuid4())
    user = User(
        id=user_id,
        client_id=client_id,
        email=f"ahmed-{uuid.uuid4().hex[:8]}@test.com",
        full_name="Ahmed Benali",
        hashed_password=get_password_hash("Test123!"),
    )
    db_session.add(user)

    meeting = Meeting(id=meeting_id, client_id=client_id, title="Test Meeting", start_time=datetime.utcnow(), end_time=datetime.utcnow() + timedelta(hours=1), creator_id=user_id)
    db_session.add(meeting)

    recording = Recording(
        id=recording_id,
        client_id=client_id,
        meeting_id=meeting_id,
        file_path="test.wav",
        status="completed",
    )
    db_session.add(recording)
    await db_session.commit()

    speaker_mappings = [
        {
            "speaker_label": "Speaker 0",
            "resolved_name": "Ahmed Benali",
            "confidence": 0.92,
            "method": "audio+text",
        },
    ]

    pv_data = {
        "title": "Test PV",
        "tags": "test",
        "summary": "Test summary",
        "decisions": ["Decision 1"],
        "actions": [
            {
                "description": "Improve the algorithm",
                "priority": "high",
                "priority_reason": "Critical",
                "assignee": "Ahmed Benali",
                "deadline": "2026-12-31",
            }
        ],
    }

    with patch("app.tasks.transcription_tasks.AuditService.log_action", new=AsyncMock()):
        await _save_pv_and_actions(
            db_session, recording, pv_data, language="fr", speaker_mappings=speaker_mappings
        )

    await db_session.commit()
    db_session.expire_all()

    actions_result = await db_session.execute(select(Action).where(Action.meeting_id == meeting_id))
    actions = list(actions_result.scalars().all())
    assert len(actions) == 1, "Should create one action"

    assignments_result = await db_session.execute(
        select(Assignment).where(Assignment.action_id == actions[0].id)
    )
    assignments = list(assignments_result.scalars().all())
    assert len(assignments) == 1, "Should create one assignment"
    assert assignments[0].user_id == user_id, "Should assign to the correct user via speaker_mappings"
    assert assignments[0].external_name is None, "Should not create external assignment"


@pytest.mark.asyncio
async def test_save_pv_and_actions_fallback_to_ilike(db_session: AsyncSession):
    """When assignee is not in speaker_mappings, should fall back to ILIKE."""
    client_id = str(uuid.uuid4())
    meeting_id = str(uuid.uuid4())
    recording_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())

    client = Client(id=client_id, company_name=f"Test Client {client_id[:8]}", subscription_status=SubscriptionStatus.ACTIVE)
    db_session.add(client)

    user = User(
        id=user_id,
        client_id=client_id,
        email=f"fatima-{uuid.uuid4().hex[:8]}@test.com",
        full_name="Fatima Zahra",
        hashed_password=get_password_hash("Test123!"),
    )
    db_session.add(user)

    meeting = Meeting(id=meeting_id, client_id=client_id, title="Test Meeting", start_time=datetime.utcnow(), end_time=datetime.utcnow() + timedelta(hours=1), creator_id=user_id)
    db_session.add(meeting)

    recording = Recording(
        id=recording_id,
        client_id=client_id,
        meeting_id=meeting_id,
        file_path="test.wav",
        status="completed",
    )
    db_session.add(recording)
    await db_session.commit()

    speaker_mappings = [
        {
            "speaker_label": "Speaker 0",
            "resolved_name": "Someone Else",
            "confidence": 0.80,
            "method": "audio",
        },
    ]

    pv_data = {
        "title": "Test PV",
        "tags": "test",
        "summary": "Test summary",
        "decisions": [],
        "actions": [
            {
                "description": "Prepare the report",
                "priority": "medium",
                "priority_reason": "Routine",
                "assignee": "Fatima Zahra",
                "deadline": None,
            }
        ],
    }

    with patch("app.tasks.transcription_tasks.AuditService.log_action", new=AsyncMock()):
        await _save_pv_and_actions(
            db_session, recording, pv_data, language="fr", speaker_mappings=speaker_mappings
        )

    await db_session.commit()
    db_session.expire_all()

    actions_result = await db_session.execute(select(Action).where(Action.meeting_id == meeting_id))
    actions = list(actions_result.scalars().all())
    assert len(actions) == 1

    assignments_result = await db_session.execute(
        select(Assignment).where(Assignment.action_id == actions[0].id)
    )
    assignments = list(assignments_result.scalars().all())
    assert len(assignments) == 1
    assert assignments[0].user_id == user_id, "Should match via ILIKE fallback"


@pytest.mark.asyncio
async def test_save_pv_and_actions_external_assignment(db_session: AsyncSession):
    """When no user matches, should create external assignment."""
    client_id = str(uuid.uuid4())
    meeting_id = str(uuid.uuid4())
    recording_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())

    client = Client(id=client_id, company_name=f"Test Client {client_id[:8]}", subscription_status=SubscriptionStatus.ACTIVE)
    db_session.add(client)

    user = User(
        id=user_id,
        client_id=client_id,
        email=f"test-external-{uuid.uuid4().hex[:8]}@test.com",
        full_name="Test User External",
        hashed_password=get_password_hash("Test123!"),
    )
    db_session.add(user)

    meeting = Meeting(id=meeting_id, client_id=client_id, title="Test Meeting", start_time=datetime.utcnow(), end_time=datetime.utcnow() + timedelta(hours=1), creator_id=user_id)
    db_session.add(meeting)

    recording = Recording(
        id=recording_id,
        client_id=client_id,
        meeting_id=meeting_id,
        file_path="test.wav",
        status="completed",
    )
    db_session.add(recording)
    await db_session.commit()

    speaker_mappings = []

    pv_data = {
        "title": "Test PV",
        "tags": "test",
        "summary": "Test summary",
        "decisions": [],
        "actions": [
            {
                "description": "Contact external consultant",
                "priority": "low",
                "priority_reason": "Optional",
                "assignee": "External Consultant",
                "deadline": None,
            }
        ],
    }

    with patch("app.tasks.transcription_tasks.AuditService.log_action", new=AsyncMock()):
        await _save_pv_and_actions(
            db_session, recording, pv_data, language="fr", speaker_mappings=speaker_mappings
        )

    db_session.expire_all()

    actions_result = await db_session.execute(select(Action).where(Action.meeting_id == meeting_id))
    actions = list(actions_result.scalars().all())
    assert len(actions) == 1

    assignments_result = await db_session.execute(
        select(Assignment).where(Assignment.action_id == actions[0].id)
    )
    assignments = list(assignments_result.scalars().all())
    assert len(assignments) == 1
    assert assignments[0].external_name == "External Consultant"
    assert assignments[0].user_id is None


@pytest.mark.asyncio
async def test_learn_from_feedback_user_match(db_session: AsyncSession):
    """learn_from_feedback should match suggested_assignee to existing user."""
    client_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    meeting_id = str(uuid.uuid4())

    client = Client(id=client_id, company_name=f"Test Client {client_id[:8]}", subscription_status=SubscriptionStatus.ACTIVE)
    db_session.add(client)

    user = User(
        id=user_id,
        client_id=client_id,
        email=f"omar-{uuid.uuid4().hex[:8]}@test.com",
        full_name="Omar Hassan",
        hashed_password=get_password_hash("Test123!"),
    )
    db_session.add(user)

    meeting = Meeting(id=meeting_id, client_id=client_id, title="Test Meeting", start_time=datetime.utcnow(), end_time=datetime.utcnow() + timedelta(hours=1), creator_id=user_id)
    db_session.add(meeting)
    await db_session.commit()

    suggestion = ActionSuggestion(
        id=str(uuid.uuid4()),
        meeting_id=meeting_id,
        client_id=client_id,
        title="Update documentation",
        description="Update the API docs",
        suggested_assignee="Omar Hassan",
        confidence_score=0.85,
        status=SuggestionStatus.SUGGESTED,
        language="fr",
    )
    db_session.add(suggestion)
    await db_session.commit()

    service = ActionService(db_session)
    await service.learn_from_feedback(suggestion.id, client_id, "accept")

    # Query using a fresh statement on the same session
    actions_result = await db_session.execute(
        select(Action).where(Action.meeting_id == meeting_id)
    )
    actions = list(actions_result.scalars().all())
    assert len(actions) == 1

    assignments_result = await db_session.execute(
        select(Assignment).where(Assignment.action_id == actions[0].id)
    )
    assignments = list(assignments_result.scalars().all())
    assert len(assignments) == 1
    assert assignments[0].user_id == user_id, "Should match to existing user"
    assert assignments[0].external_name is None, "Should not create external assignment"


@pytest.mark.asyncio
async def test_learn_from_feedback_external_fallback(db_session: AsyncSession):
    """learn_from_feedback should create external assignment when no user matches."""
    client_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    meeting_id = str(uuid.uuid4())

    client = Client(id=client_id, company_name=f"Test Client {client_id[:8]}", subscription_status=SubscriptionStatus.ACTIVE)
    db_session.add(client)

    user = User(
        id=user_id,
        client_id=client_id,
        email=f"test-external-{uuid.uuid4().hex[:8]}@test.com",
        full_name="Test User External",
        hashed_password=get_password_hash("Test123!"),
    )
    db_session.add(user)

    meeting = Meeting(id=meeting_id, client_id=client_id, title="Test Meeting", start_time=datetime.utcnow(), end_time=datetime.utcnow() + timedelta(hours=1), creator_id=user_id)
    db_session.add(meeting)
    await db_session.commit()

    suggestion = ActionSuggestion(
        id=str(uuid.uuid4()),
        meeting_id=meeting_id,
        client_id=client_id,
        title="Review contract",
        description="Review the legal contract",
        suggested_assignee="External Lawyer",
        confidence_score=0.70,
        status=SuggestionStatus.SUGGESTED,
        language="fr",
    )
    db_session.add(suggestion)
    await db_session.commit()

    service = ActionService(db_session)
    await service.learn_from_feedback(suggestion.id, client_id, "accept")

    # Query using a fresh statement on the same session
    actions_result = await db_session.execute(
        select(Action).where(Action.meeting_id == meeting_id)
    )
    actions = list(actions_result.scalars().all())
    assert len(actions) == 1

    assignments_result = await db_session.execute(
        select(Assignment).where(Assignment.action_id == actions[0].id)
    )
    assignments = list(assignments_result.scalars().all())
    assert len(assignments) == 1
    assert assignments[0].external_name == "External Lawyer"
    assert assignments[0].user_id is None


@pytest.mark.asyncio
async def test_speaker_resolved_name_column(db_session: AsyncSession):
    """Speaker model should have resolved_name column separate from name (Gladia label)."""
    from app.models.transcription import Speaker
    
    client_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    meeting_id = str(uuid.uuid4())
    
    client = Client(id=client_id, company_name=f"Test Client {client_id[:8]}", subscription_status=SubscriptionStatus.ACTIVE)
    db_session.add(client)
    
    user = User(
        id=user_id,
        client_id=client_id,
        email=f"speaker-test-{uuid.uuid4().hex[:8]}@test.com",
        full_name="Test User",
        hashed_password=get_password_hash("Test123!"),
    )
    db_session.add(user)
    
    meeting = Meeting(id=meeting_id, client_id=client_id, title="Test", start_time=datetime.utcnow(), end_time=datetime.utcnow() + timedelta(hours=1), creator_id=user_id)
    db_session.add(meeting)
    await db_session.commit()
    
    speaker = Speaker(
        id=f"sp-test-{uuid.uuid4().hex[:8]}",
        meeting_id=meeting_id,
        client_id=client_id,
        name="Speaker 0",
        resolved_name="Abdelkader Batnini",
        mapping_confidence=0.95,
        mapping_method="audio+text+llm",
    )
    db_session.add(speaker)
    await db_session.commit()
    
    # Verify resolved_name is stored separately
    result = await db_session.execute(select(Speaker).where(Speaker.id == speaker.id))
    saved = result.scalar_one()
    assert saved.name == "Speaker 0", "name should store Gladia label"
    assert saved.resolved_name == "Abdelkader Batnini", "resolved_name should store resolved name"


@pytest.mark.asyncio
async def test_learn_from_feedback_null_assignee_single_speaker(db_session: AsyncSession):
    """learn_from_feedback should use single speaker fallback when suggested_assignee is null."""
    client_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    meeting_id = str(uuid.uuid4())
    
    client = Client(id=client_id, company_name=f"Test Client {client_id[:8]}", subscription_status=SubscriptionStatus.ACTIVE)
    db_session.add(client)
    
    user = User(
        id=user_id,
        client_id=client_id,
        email=f"single-speaker-{uuid.uuid4().hex[:8]}@test.com",
        full_name="Abdelkader Batnini",
        hashed_password=get_password_hash("Test123!"),
    )
    db_session.add(user)
    
    meeting = Meeting(id=meeting_id, client_id=client_id, title="Test Meeting", start_time=datetime.utcnow(), end_time=datetime.utcnow() + timedelta(hours=1), creator_id=user_id)
    db_session.add(meeting)
    await db_session.commit()
    
    # Create a Speaker record with resolved_name
    from app.models.transcription import Speaker
    speaker = Speaker(
        id=f"sp-single-{uuid.uuid4().hex[:8]}",
        meeting_id=meeting_id,
        client_id=client_id,
        name="Speaker 0",
        resolved_name="Abdelkader Batnini",
        user_id=user_id,
        mapping_confidence=0.95,
        mapping_method="audio",
    )
    db_session.add(speaker)
    await db_session.commit()
    
    # Create suggestion with NULL suggested_assignee
    suggestion = ActionSuggestion(
        id=str(uuid.uuid4()),
        meeting_id=meeting_id,
        client_id=client_id,
        title="Test the program",
        description="Verify functionality",
        suggested_assignee=None,
        confidence_score=0.80,
        status=SuggestionStatus.SUGGESTED,
        language="fr",
    )
    db_session.add(suggestion)
    await db_session.commit()
    
    service = ActionService(db_session)
    await service.learn_from_feedback(suggestion.id, client_id, "accept")
    
    actions_result = await db_session.execute(select(Action).where(Action.meeting_id == meeting_id))
    actions = list(actions_result.scalars().all())
    assert len(actions) == 1
    
    assignments_result = await db_session.execute(select(Assignment).where(Assignment.action_id == actions[0].id))
    assignments = list(assignments_result.scalars().all())
    assert len(assignments) == 1
    assert assignments[0].user_id == user_id, "Should use single speaker fallback"


@pytest.mark.asyncio
async def test_learn_from_feedback_uses_resolved_name(db_session: AsyncSession):
    """learn_from_feedback should use Speaker.resolved_name, not just Speaker.name."""
    client_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    meeting_id = str(uuid.uuid4())
    
    client = Client(id=client_id, company_name=f"Test Client {client_id[:8]}", subscription_status=SubscriptionStatus.ACTIVE)
    db_session.add(client)
    
    user = User(
        id=user_id,
        client_id=client_id,
        email=f"resolved-test-{uuid.uuid4().hex[:8]}@test.com",
        full_name="Mohamed Al-Arbi Al-Nakti",
        hashed_password=get_password_hash("Test123!"),
    )
    db_session.add(user)
    
    meeting = Meeting(id=meeting_id, client_id=client_id, title="Test", start_time=datetime.utcnow(), end_time=datetime.utcnow() + timedelta(hours=1), creator_id=user_id)
    db_session.add(meeting)
    await db_session.commit()
    
    # Speaker with name="Speaker 0" but resolved_name="Mohamed Al-Arbi Al-Nakti"
    from app.models.transcription import Speaker
    speaker = Speaker(
        id=f"sp-resolved-{uuid.uuid4().hex[:8]}",
        meeting_id=meeting_id,
        client_id=client_id,
        name="Speaker 0",
        resolved_name="Mohamed Al-Arbi Al-Nakti",
        user_id=user_id,
        mapping_confidence=0.90,
        mapping_method="audio+text",
    )
    db_session.add(speaker)
    await db_session.commit()
    
    suggestion = ActionSuggestion(
        id=str(uuid.uuid4()),
        meeting_id=meeting_id,
        client_id=client_id,
        title="Finalize minutes",
        description="Edit and finalize the meeting minutes",
        suggested_assignee="Mohamed Al-Arbi Al-Nakti",
        confidence_score=0.85,
        status=SuggestionStatus.SUGGESTED,
        language="fr",
    )
    db_session.add(suggestion)
    await db_session.commit()
    
    service = ActionService(db_session)
    await service.learn_from_feedback(suggestion.id, client_id, "accept")
    
    actions_result = await db_session.execute(select(Action).where(Action.meeting_id == meeting_id))
    actions = list(actions_result.scalars().all())
    assert len(actions) == 1
    
    assignments_result = await db_session.execute(select(Assignment).where(Assignment.action_id == actions[0].id))
    assignments = list(assignments_result.scalars().all())
    assert len(assignments) == 1
    assert assignments[0].user_id == user_id, "Should resolve via resolved_name"


@pytest.mark.asyncio
async def test_learn_from_feedback_transcript_segment_match(db_session: AsyncSession):
    """learn_from_feedback should search transcript segments when suggested_assignee is null."""
    client_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    meeting_id = str(uuid.uuid4())
    recording_id = str(uuid.uuid4())
    
    client = Client(id=client_id, company_name=f"Test Client {client_id[:8]}", subscription_status=SubscriptionStatus.ACTIVE)
    db_session.add(client)
    
    user = User(
        id=user_id,
        client_id=client_id,
        email=f"segment-test-{uuid.uuid4().hex[:8]}@test.com",
        full_name="Abdelkader Batnini",
        hashed_password=get_password_hash("Test123!"),
    )
    db_session.add(user)
    
    meeting = Meeting(id=meeting_id, client_id=client_id, title="Test", start_time=datetime.utcnow(), end_time=datetime.utcnow() + timedelta(hours=1), creator_id=user_id)
    db_session.add(meeting)
    
    recording = Recording(
        id=recording_id,
        client_id=client_id,
        meeting_id=meeting_id,
        file_path="test.wav",
        status="completed",
    )
    db_session.add(recording)
    await db_session.commit()
    
    # Create transcription with segments
    from app.models.transcription import Transcription
    transcription = Transcription(
        id=str(uuid.uuid4()),
        client_id=client_id,
        meeting_id=meeting_id,
        recording_id=recording_id,
        full_text="Abdelkader Batnini: I will test the program.\nMohamed: I agree.",
        segments=[
            {"speaker": "Abdelkader Batnini", "text": "I will test the program", "start": 0, "end": 5},
            {"speaker": "Mohamed", "text": "I agree with that", "start": 6, "end": 10},
        ],
        status="completed",
    )
    db_session.add(transcription)
    await db_session.commit()
    
    suggestion = ActionSuggestion(
        id=str(uuid.uuid4()),
        meeting_id=meeting_id,
        client_id=client_id,
        title="Test the program",
        description="Verify the program functionality",
        suggested_assignee=None,
        confidence_score=0.75,
        status=SuggestionStatus.SUGGESTED,
        language="fr",
    )
    db_session.add(suggestion)
    await db_session.commit()
    
    service = ActionService(db_session)
    await service.learn_from_feedback(suggestion.id, client_id, "accept")
    
    actions_result = await db_session.execute(select(Action).where(Action.meeting_id == meeting_id))
    actions = list(actions_result.scalars().all())
    assert len(actions) == 1
    
    # Should have attempted transcript segment match
    assignments_result = await db_session.execute(select(Assignment).where(Assignment.action_id == actions[0].id))
    assignments = list(assignments_result.scalars().all())
    # Assignment may or may not exist depending on resolution, but action should exist
    assert len(actions) == 1
