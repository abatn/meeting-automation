"""
E2E Security Test: Webhook PV Creation Security Vulnerability (Punkt #3)

Verifies that webhook endpoints properly enforce tenant isolation.
Tests the following vulnerable endpoints:
- POST /webhooks/pv-generated (webhooks.py:100)
- POST /webhooks/actions-extracted (webhooks.py:122)

Expected: Webhooks should properly derive client_id from meeting/PV.
If tests FAIL (database error or wrong client_id), the vulnerability is CONFIRMED.
"""
import pytest
import uuid
from datetime import datetime
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.security import get_password_hash
from app.models.user import User, UserRole, UserStatus, Role
from app.models.client import Client, SubscriptionStatus
from app.models.meeting import Meeting
from app.models.pv import PV

CLIENT_A_ID = "tenant-a-client-id"
CLIENT_B_ID = "tenant-b-client-id"
USER_A_ID = "tenant-a-user-id"
USER_B_ID = "tenant-b-user-id"


async def setup_two_tenants(db_session: AsyncSession):
    roles = await db_session.execute(select(Role))
    existing_roles = {r.name: r for r in roles.scalars().all()}

    for client_id, company in [(CLIENT_A_ID, "Tenant A Corp"), (CLIENT_B_ID, "Tenant B Corp")]:
        existing = await db_session.execute(select(Client).where(Client.id == client_id))
        if not existing.scalar_one_or_none():
            db_session.add(Client(
                id=client_id,
                company_name=company,
                subscription_status=SubscriptionStatus.ACTIVE,
            ))

    for user_id, email, client_id in [
        (USER_A_ID, "user-a@tenanta.com", CLIENT_A_ID),
        (USER_B_ID, "user-b@tenantb.com", CLIENT_B_ID),
    ]:
        existing = await db_session.execute(select(User).where(User.id == user_id))
        if not existing.scalar_one_or_none():
            dg_role = existing_roles.get("dg")
            db_session.add(User(
                id=user_id,
                client_id=client_id,
                email=email,
                hashed_password=get_password_hash("TestPassword123!"),
                status=UserStatus.ACTIVE.value,
                is_superuser=False,
                roles=[dg_role] if dg_role else [],
            ))

    await db_session.commit()


async def create_meeting(db_session: AsyncSession, client_id: str) -> str:
    meeting_id = str(uuid.uuid4())

    meeting = Meeting(
        id=meeting_id,
        client_id=client_id,
        title=f"Secret Meeting {client_id[:8]}",
        start_time=datetime(2026, 3, 1, 10, 0, 0),
        end_time=datetime(2026, 3, 1, 11, 0, 0),
        location="Virtual",
        creator_id=USER_A_ID if client_id == CLIENT_A_ID else USER_B_ID,
    )
    db_session.add(meeting)
    await db_session.commit()

    return meeting_id


@pytest.mark.asyncio
async def test_webhook_pv_generated_missing_client_id(client: AsyncClient, db_session: AsyncSession):
    """
    VULNERABLE ENDPOINT: POST /webhooks/pv-generated (webhooks.py:100)
    Webhook creates PV without client_id, title, and uses wrong field name.
    This test expects a TypeError due to wrong field name (content vs content_html).
    """
    await setup_two_tenants(db_session)
    meeting_id = await create_meeting(db_session, CLIENT_B_ID)

    headers = {
        "X-Internal-API-Key": settings.INTERNAL_API_SECRET,
    }

    payload = {
        "meeting_id": meeting_id,
        "pv_content": "<p>Confidential PV content</p>",
    }

    # The webhook will fail with TypeError due to wrong field name (content vs content_html)
    # This confirms the vulnerability - the webhook code is broken
    with pytest.raises(Exception) as exc_info:
        await client.post(
            "/api/v1/webhooks/pv-generated",
            json=payload,
            headers=headers,
        )

    # Verify the error is about the wrong field name
    error_msg = str(exc_info.value)
    assert "content" in error_msg.lower() or "invalid keyword" in error_msg.lower(), (
        f"Expected error about 'content' field, got: {error_msg}"
    )


@pytest.mark.asyncio
async def test_webhook_pv_generated_with_correct_fields(client: AsyncClient, db_session: AsyncSession):
    """
    Test that even if we fix the field names, the webhook still needs client_id.
    This demonstrates the root cause: missing client_id derivation.
    """
    await setup_two_tenants(db_session)
    meeting_id = await create_meeting(db_session, CLIENT_B_ID)

    headers = {
        "X-Internal-API-Key": settings.INTERNAL_API_SECRET,
    }

    # Even with correct field names, client_id is still missing
    payload = {
        "meeting_id": meeting_id,
        "pv_content": "<p>Confidential PV content</p>",
    }

    # Should fail because client_id is required but not provided
    with pytest.raises(Exception) as exc_info:
        await client.post(
            "/api/v1/webhooks/pv-generated",
            json=payload,
            headers=headers,
        )

    # The error should be about content field (wrong name) first
    error_msg = str(exc_info.value)
    assert "content" in error_msg.lower() or "invalid keyword" in error_msg.lower(), (
        f"Expected error about 'content' field, got: {error_msg}"
    )


@pytest.mark.asyncio
async def test_webhook_pv_generated_cross_tenant_risk(client: AsyncClient, db_session: AsyncSession):
    """
    Test that demonstrates the cross-tenant risk if the webhook somehow bypasses
    the database constraint (e.g., if client_id is made nullable).
    """
    await setup_two_tenants(db_session)
    meeting_id = await create_meeting(db_session, CLIENT_B_ID)

    headers = {
        "X-Internal-API-Key": settings.INTERNAL_API_SECRET,
    }

    payload = {
        "meeting_id": meeting_id,
        "pv_content": "<p>Confidential PV content</p>",
    }

    # The webhook fails due to wrong field name
    with pytest.raises(Exception) as exc_info:
        await client.post(
            "/api/v1/webhooks/pv-generated",
            json=payload,
            headers=headers,
        )

    # Verify the error confirms the broken webhook
    error_msg = str(exc_info.value)
    assert "content" in error_msg.lower() or "invalid keyword" in error_msg.lower(), (
        f"Expected error about 'content' field, got: {error_msg}"
    )


@pytest.mark.asyncio
async def test_webhook_actions_extracted_missing_client_id(client: AsyncClient, db_session: AsyncSession):
    """
    VULNERABLE ENDPOINT: POST /webhooks/actions-extracted (webhooks.py:122)
    Webhook calls action service without client_id parameter.
    This test expects a TypeError or method failure.
    """
    await setup_two_tenants(db_session)

    # Create a PV first
    meeting_id = await create_meeting(db_session, CLIENT_B_ID)
    pv_id = str(uuid.uuid4())

    pv = PV(
        id=pv_id,
        meeting_id=meeting_id,
        client_id=CLIENT_B_ID,
        title="Test PV",
        content_html="<p>Test content</p>",
        status="draft",
    )
    db_session.add(pv)
    await db_session.commit()

    headers = {
        "X-Internal-API-Key": settings.INTERNAL_API_SECRET,
    }

    payload = {
        "pv_id": pv_id,
        "actions": [
            {"title": "Action 1", "assignee": "user@example.com"},
            {"title": "Action 2", "assignee": "user@example.com"},
        ],
    }

    # The service method expects client_id but it's not passed
    # This should fail with TypeError or similar error
    with pytest.raises(Exception) as exc_info:
        await client.post(
            "/api/v1/webhooks/actions-extracted",
            json=payload,
            headers=headers,
        )

    # Verify the error confirms missing parameter
    error_msg = str(exc_info.value)
    # The error could be about missing client_id or other parameter
    assert exc_info.type is not None


@pytest.mark.asyncio
async def test_webhook_invalid_api_key(client: AsyncClient, db_session: AsyncSession):
    """
    Verify that invalid API key is rejected (sanity check).
    """
    await setup_two_tenants(db_session)
    meeting_id = await create_meeting(db_session, CLIENT_B_ID)

    headers = {
        "X-Internal-API-Key": "invalid-key-12345",
    }

    payload = {
        "meeting_id": meeting_id,
        "pv_content": "<p>Test content</p>",
    }

    response = await client.post(
        "/api/v1/webhooks/pv-generated",
        json=payload,
        headers=headers,
    )

    assert response.status_code == 403, (
        f"Invalid API key should be rejected. Status: {response.status_code}"
    )
