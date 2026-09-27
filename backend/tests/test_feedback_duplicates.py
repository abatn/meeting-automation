"""
Duplikat-Check in learn_from_feedback (Option b).

learn_from_feedback darf bei Accept KEINE zweite Action erzeugen, wenn das
Meeting bereits eine inhaltlich gleiche Action hat (PV erzeugt FR-Actions,
Suggestionen kommen als EN-Titel aus einem zweiten Mistral-Lauf).
"""

import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash
from app.models.action import (
    Action,
    ActionStatus,
    ActionSuggestion,
    Assignment,
    SuggestionStatus,
)
from app.models.audit_log import AuditLog
from app.models.client import Client, SubscriptionStatus
from app.models.meeting import Meeting
from app.models.user import User
from app.services.action_service import (
    ActionService,
    _normalize_title,
    _title_similarity,
)

RESOLUTION = {"assignee_name": "Omar Hassan", "confidence": 0.9, "source": "test_stub"}


async def _setup_meeting(
    db_session: AsyncSession, client_id: str, user_id: str, meeting_id: str
) -> None:
    db_session.add(
        Client(
            id=client_id,
            company_name=f"Test Client {client_id[:8]}",
            subscription_status=SubscriptionStatus.ACTIVE,
        )
    )
    db_session.add(
        User(
            id=user_id,
            client_id=client_id,
            email=f"dup-{uuid.uuid4().hex[:8]}@test.com",
            full_name="Omar Hassan",
            hashed_password=get_password_hash("Test123!"),
        )
    )
    db_session.add(
        Meeting(
            id=meeting_id,
            client_id=client_id,
            title="Dup Test Meeting",
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow() + timedelta(hours=1),
            creator_id=user_id,
        )
    )
    await db_session.commit()


async def _add_suggestion(
    db_session: AsyncSession, client_id: str, meeting_id: str, title: str, language: str
) -> str:
    sid = str(uuid.uuid4())
    db_session.add(
        ActionSuggestion(
            id=sid,
            meeting_id=meeting_id,
            client_id=client_id,
            title=title,
            description=title,
            suggested_assignee="Omar Hassan",
            confidence_score=0.85,
            status=SuggestionStatus.SUGGESTED,
            language=language,
        )
    )
    await db_session.commit()
    return sid


async def _add_action(
    db_session: AsyncSession, client_id: str, meeting_id: str, title: str
) -> str:
    aid = str(uuid.uuid4())
    db_session.add(
        Action(
            id=aid,
            client_id=client_id,
            meeting_id=meeting_id,
            title=title,
            description=title,
            status=ActionStatus.PENDING,
            priority="medium",
        )
    )
    await db_session.commit()
    return aid


async def _learn(
    service: ActionService, suggestion_id: str, client_id: str, translated=None
) -> None:
    with (
        patch.object(
            ActionService,
            "_resolve_assignee_with_full_signals",
            new=AsyncMock(return_value=dict(RESOLUTION)),
        ),
        patch.object(
            ActionService,
            "translate_texts",
            new=AsyncMock(return_value=translated or []),
        ),
    ):
        await service.learn_from_feedback(suggestion_id, client_id, "accept")


@pytest.mark.asyncio
async def test_creates_action_when_no_counterpart(db_session: AsyncSession):
    """Kein Gegenstück -> Action WIRD angelegt (Rückfallebene)."""
    client_id, user_id, meeting_id = (
        str(uuid.uuid4()),
        str(uuid.uuid4()),
        str(uuid.uuid4()),
    )
    await _setup_meeting(db_session, client_id, user_id, meeting_id)
    sid = await _add_suggestion(
        db_session, client_id, meeting_id, "Ship quarterly report", "en"
    )

    service = ActionService(db_session)
    await _learn(service, sid, client_id)

    actions = (
        (
            await db_session.execute(
                select(Action).where(Action.meeting_id == meeting_id)
            )
        )
        .scalars()
        .all()
    )
    assert len(actions) == 1
    suggestion = (
        await db_session.execute(
            select(ActionSuggestion).where(ActionSuggestion.id == sid)
        )
    ).scalar_one()
    assert suggestion.status == SuggestionStatus.ACCEPTED
    assignments = (
        (
            await db_session.execute(
                select(Assignment).where(Assignment.action_id == actions[0].id)
            )
        )
        .scalars()
        .all()
    )
    assert len(assignments) == 1


@pytest.mark.asyncio
async def test_skips_duplicate_via_translation(db_session: AsyncSession):
    """EN-Suggestion + FR-PV-Action + passende Übersetzung -> KEINE neue Action, Assignment-Lückenschluss."""
    client_id, user_id, meeting_id = (
        str(uuid.uuid4()),
        str(uuid.uuid4()),
        str(uuid.uuid4()),
    )
    await _setup_meeting(db_session, client_id, user_id, meeting_id)
    existing_id = await _add_action(
        db_session, client_id, meeting_id, "Mettre à jour la documentation technique"
    )
    sid = await _add_suggestion(
        db_session, client_id, meeting_id, "Update the technical documentation", "en"
    )

    service = ActionService(db_session)
    await _learn(
        service, sid, client_id, translated=["Mettre à jour la documentation technique"]
    )

    actions = (
        (
            await db_session.execute(
                select(Action).where(Action.meeting_id == meeting_id)
            )
        )
        .scalars()
        .all()
    )
    assert len(actions) == 1, "Dublette darf NICHT angelegt werden"
    assert actions[0].id == existing_id
    suggestion = (
        await db_session.execute(
            select(ActionSuggestion).where(ActionSuggestion.id == sid)
        )
    ).scalar_one()
    assert suggestion.status == SuggestionStatus.ACCEPTED
    assignments = (
        (
            await db_session.execute(
                select(Assignment).where(Assignment.action_id == existing_id)
            )
        )
        .scalars()
        .all()
    )
    assert (
        len(assignments) == 1
    ), "Lückenschluss muss Assignment auf BESTEHENDE Action setzen"
    audit = (
        (
            await db_session.execute(
                select(AuditLog).where(AuditLog.action == "ACTION_ASSIGNED")
            )
        )
        .scalars()
        .all()
    )
    assert len(audit) >= 1, "Audit-Eintrag bleibt Pflicht (ISO 27001)"


@pytest.mark.asyncio
async def test_second_run_is_idempotent(db_session: AsyncSession):
    """Zweiter Lauf derselben suggestion_id erzeugt NICHTS doppelt."""
    client_id, user_id, meeting_id = (
        str(uuid.uuid4()),
        str(uuid.uuid4()),
        str(uuid.uuid4()),
    )
    await _setup_meeting(db_session, client_id, user_id, meeting_id)
    sid = await _add_suggestion(
        db_session, client_id, meeting_id, "Prepare kickoff agenda", "en"
    )

    service = ActionService(db_session)
    await _learn(service, sid, client_id)
    await _learn(service, sid, client_id)

    actions = (
        (
            await db_session.execute(
                select(Action).where(Action.meeting_id == meeting_id)
            )
        )
        .scalars()
        .all()
    )
    assert len(actions) == 1
    assignments = (await db_session.execute(select(Assignment))).scalars().all()
    assert len(assignments) == 1


@pytest.mark.asyncio
async def test_direct_normalized_match_without_translation(db_session: AsyncSession):
    """Gleiche Sprache, Unterschiede nur in Zeichensetzung/Großschreibung -> direkter Treffer, kein Übersetzungsaufruf."""
    client_id, user_id, meeting_id = (
        str(uuid.uuid4()),
        str(uuid.uuid4()),
        str(uuid.uuid4()),
    )
    await _setup_meeting(db_session, client_id, user_id, meeting_id)
    existing_id = await _add_action(
        db_session, client_id, meeting_id, "Mettre a jour la documentation"
    )
    sid = await _add_suggestion(
        db_session, client_id, meeting_id, "Mettre à JOUR la documentation !", "fr"
    )

    service = ActionService(db_session)
    with (
        patch.object(
            ActionService,
            "_resolve_assignee_with_full_signals",
            new=AsyncMock(return_value=dict(RESOLUTION)),
        ),
        patch.object(
            ActionService,
            "translate_texts",
            new=AsyncMock(
                side_effect=AssertionError(
                    "kein Übersetzungsaufruf bei direktem Treffer"
                )
            ),
        ),
    ):
        await service.learn_from_feedback(sid, client_id, "accept")

    actions = (
        (
            await db_session.execute(
                select(Action).where(Action.meeting_id == meeting_id)
            )
        )
        .scalars()
        .all()
    )
    assert len(actions) == 1
    assert actions[0].id == existing_id


def test_normalize_and_similarity_helpers():
    assert _normalize_title("Mettre à JOUR — la documentation !") == _normalize_title(
        "mettre a jour la documentation"
    )
    assert (
        _title_similarity(
            _normalize_title("Update the docs"),
            _normalize_title("Update the documentation"),
        )
        >= 0.6
    )
    assert _title_similarity("", "x") == 0.0
