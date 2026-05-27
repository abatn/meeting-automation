"""
Security Test: PVVersion Cross-Tenant Isolation Vulnerability (Punkt #1)
Folgt dem existierenden Test-Pattern aus test_pv_versioning.py
"""
import pytest
import uuid
import json
from datetime import datetime
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from jose import jwt

from app.core.config import settings
from app.core.security import get_password_hash
from app.models.user import User, UserStatus, Role
from app.models.client import Client, SubscriptionStatus
from app.models.meeting import Meeting
from app.models.pv import PV, PVVersion

OTHER_CLIENT_ID = "other-client-id"
OTHER_USER_ID = "other-user-id"


async def ensure_other_tenant(db_session: AsyncSession):
    """Erstellt Other Tenant falls nicht vorhanden"""
    result = await db_session.execute(select(Client).where(Client.id == OTHER_CLIENT_ID))
    if not result.scalar_one_or_none():
        db_session.add(Client(
            id=OTHER_CLIENT_ID,
            company_name="Other Tenant Corp",
            subscription_status=SubscriptionStatus.ACTIVE,
        ))

    roles = await db_session.execute(select(Role))
    existing_roles = {r.name: r for r in roles.scalars().all()}
    dg_role = existing_roles.get("dg")

    result = await db_session.execute(select(User).where(User.id == OTHER_USER_ID))
    if not result.scalar_one_or_none():
        db_session.add(User(
            id=OTHER_USER_ID,
            client_id=OTHER_CLIENT_ID,
            email="other@example.com",
            hashed_password=get_password_hash("TestPassword123!"),
            status=UserStatus.ACTIVE.value,
            is_superuser=False,
            roles=[dg_role] if dg_role else [],
        ))
    await db_session.commit()


def make_token(user_id: str, client_id: str) -> str:
    payload = {"sub": user_id, "client_id": client_id, "role": "dg"}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


@pytest.mark.asyncio
async def test_get_pv_version_cross_tenant_is_blocked(client: AsyncClient, db_session: AsyncSession):
    """GET /{pv_id}/versions/{version_id} sollte Cross-Tenant Zugriff verweigern"""
    await ensure_other_tenant(db_session)

    meeting_id = str(uuid.uuid4())
    pv_id = str(uuid.uuid4())

    meeting_b = Meeting(
        id=meeting_id,
        client_id="test-client-id",
        title="Tenant B Meeting",
        start_time=datetime(2026, 3, 1, 10, 0, 0),
        end_time=datetime(2026, 3, 1, 11, 0, 0),
        location="Virtual",
        creator_id="test-user-id"
    )
    db_session.add(meeting_b)

    pv_b = PV(
        id=pv_id,
        meeting_id=meeting_id,
        client_id="test-client-id",
        title="Tenant B PV",
        content_html="<p>Confidential</p>",
        status="draft"
    )
    db_session.add(pv_b)
    await db_session.flush()

    version_id = str(uuid.uuid4())
    version = PVVersion(
        id=version_id,
        pv_id=pv_id,
        version_number=1,
        snapshot_data=json.dumps({"title": "Tenant B PV", "content_html": "<p>Confidential</p>", "status": "draft"}),
        change_summary="Initial"
    )
    db_session.add(version)
    await db_session.commit()

    token_other = make_token(OTHER_USER_ID, OTHER_CLIENT_ID)
    headers_other = {"Authorization": f"Bearer {token_other}"}

    response = await client.get(
        f"/api/v1/pv/{pv_id}/versions/{version_id}",
        headers=headers_other
    )

    if response.status_code == 200:
        pytest.fail(
            f"VULNERABILITY: Cross-tenant access ALLOWED!\n"
            f"Status: {response.status_code}, Got data: {response.json()}"
        )

    assert response.status_code == 404, (
        f"Expected 404, got {response.status_code}"
    )


@pytest.mark.asyncio
async def test_restore_pv_version_cross_tenant_is_blocked(client: AsyncClient, db_session: AsyncSession):
    """POST /{pv_id}/restore/{version_id} sollte Cross-Tenant Zugriff verweigern"""
    await ensure_other_tenant(db_session)

    meeting_id = str(uuid.uuid4())
    pv_id = str(uuid.uuid4())

    meeting = Meeting(
        id=meeting_id,
        client_id="test-client-id",
        title="Tenant B Meeting",
        start_time=datetime(2026, 3, 1, 10, 0, 0),
        end_time=datetime(2026, 3, 1, 11, 0, 0),
        location="Virtual",
        creator_id="test-user-id"
    )
    db_session.add(meeting)

    pv = PV(
        id=pv_id,
        meeting_id=meeting_id,
        client_id="test-client-id",
        title="Tenant B PV",
        content_html="<p>Original</p>",
        status="draft"
    )
    db_session.add(pv)
    await db_session.flush()

    version_id = str(uuid.uuid4())
    version = PVVersion(
        id=version_id,
        pv_id=pv_id,
        version_number=1,
        snapshot_data=json.dumps({"title": "Tenant B PV", "content_html": "<p>Original</p>", "status": "draft"}),
        change_summary="Initial"
    )
    db_session.add(version)
    await db_session.commit()

    token_other = make_token(OTHER_USER_ID, OTHER_CLIENT_ID)
    headers_other = {"Authorization": f"Bearer {token_other}"}

    response = await client.post(
        f"/api/v1/pv/{pv_id}/restore/{version_id}",
        headers=headers_other
    )

    if response.status_code == 200:
        pytest.fail(f"VULNERABILITY: Cross-tenant restore ALLOWED!")

    assert response.status_code in [403, 404], (
        f"Expected 403/404, got {response.status_code}"
    )


@pytest.mark.asyncio
async def test_list_pv_versions_secure(client: AsyncClient, db_session: AsyncSession):
    """GET /{pv_id}/versions ist SECURE - PV ownership wird geprüft"""
    await ensure_other_tenant(db_session)

    meeting_id = str(uuid.uuid4())
    pv_id = str(uuid.uuid4())

    meeting = Meeting(
        id=meeting_id,
        client_id="test-client-id",
        title="Test Meeting",
        start_time=datetime(2026, 3, 1, 10, 0, 0),
        end_time=datetime(2026, 3, 1, 11, 0, 0),
        location="Virtual",
        creator_id="test-user-id"
    )
    db_session.add(meeting)

    pv = PV(
        id=pv_id,
        meeting_id=meeting_id,
        client_id="test-client-id",
        title="Test PV",
        content_html="<p>Content</p>",
        status="draft"
    )
    db_session.add(pv)
    await db_session.flush()

    version = PVVersion(
        id=str(uuid.uuid4()),
        pv_id=pv_id,
        version_number=1,
        snapshot_data=json.dumps({"title": "Test PV", "content_html": "<p>Content</p>", "status": "draft"}),
        change_summary="Initial"
    )
    db_session.add(version)
    await db_session.commit()

    token_other = make_token(OTHER_USER_ID, OTHER_CLIENT_ID)
    headers_other = {"Authorization": f"Bearer {token_other}"}

    response = await client.get(f"/api/v1/pv/{pv_id}/versions", headers=headers_other)

    assert response.status_code == 404, (
        f"Cross-tenant list should be blocked! Got: {response.status_code}"
    )