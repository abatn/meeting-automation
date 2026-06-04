"""
E2E Security Test: Automation Endpoints Cross-Tenant Isolation Vulnerability (Punkt #2)

Verifies that automation endpoints properly enforce tenant isolation.
Tests the following vulnerable endpoints:
- GET /automation/meeting/{meeting_id} (reports.py:115-136)
- GET /automation/pdf/{meeting_id} (reports.py:139-162)

Expected: Cross-tenant access SHOULD be denied (403/404).
If tests FAIL (returns 200), the vulnerability is CONFIRMED.
"""
import pytest
import uuid
from datetime import datetime
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from jose import jwt

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


async def create_meeting_with_pv(db_session: AsyncSession, client_id: str) -> dict:
    meeting_id = str(uuid.uuid4())
    pv_id = str(uuid.uuid4())

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
    await db_session.flush()

    pv = PV(
        id=pv_id,
        meeting_id=meeting_id,
        client_id=client_id,
        title=f"Secret PV for {client_id[:8]}",
        content_html=f"<p>Confidential content for {client_id}</p>",
        status="draft",
    )
    db_session.add(pv)
    await db_session.commit()

    return {"meeting_id": meeting_id, "pv_id": pv_id}


@pytest.mark.asyncio
async def test_automation_meeting_cross_tenant_vulnerability(client: AsyncClient, db_session: AsyncSession):
    """
    VULNERABLE ENDPOINT: GET /automation/meeting/{meeting_id} (reports.py:124)
    Client A should NOT be able to access Client B's meeting via automation endpoint.
    If this test PASSES (status 200), the vulnerability is CONFIRMED.
    """
    await setup_two_tenants(db_session)
    tenant_b_data = await create_meeting_with_pv(db_session, CLIENT_B_ID)

    headers = {
        "X-Internal-API-Key": settings.INTERNAL_API_SECRET,
    }

    response = await client.get(
        f"/api/v1/reports/automation/meeting/{tenant_b_data['meeting_id']}?client_id={CLIENT_A_ID}",
        headers=headers,
    )

    if response.status_code == 200:
        meeting_data = response.json()
        pytest.fail(
            f"VULNERABILITY CONFIRMED: Automation endpoint allows cross-tenant meeting access!\n"
            f"Status: 200\n"
            f"Meeting data: {meeting_data}\n"
            f"VULNERABLE LINE: reports.py:124 - No client_id filter on Meeting query"
        )
    else:
        assert response.status_code in [403, 404], (
            f"Unexpected status: {response.status_code}"
        )


@pytest.mark.asyncio
async def test_automation_pdf_cross_tenant_vulnerability(client: AsyncClient, db_session: AsyncSession):
    """
    VULNERABLE ENDPOINT: GET /automation/pdf/{meeting_id} (reports.py:152)
    Client A should NOT be able to access Client B's PV PDF via automation endpoint.
    If this test PASSES (status 200), the vulnerability is CONFIRMED.
    """
    await setup_two_tenants(db_session)
    tenant_b_data = await create_meeting_with_pv(db_session, CLIENT_B_ID)

    headers = {
        "X-Internal-API-Key": settings.INTERNAL_API_SECRET,
    }

    response = await client.get(
        f"/api/v1/reports/automation/pdf/{tenant_b_data['meeting_id']}?client_id={CLIENT_A_ID}",
        headers=headers,
    )

    if response.status_code == 200:
        pytest.fail(
            f"VULNERABILITY CONFIRMED: Automation endpoint allows cross-tenant PDF access!\n"
            f"Status: 200\n"
            f"Response: {response.headers}\n"
            f"VULNERABLE LINE: reports.py:152 - No client_id filter on PV query"
        )
    else:
        assert response.status_code in [403, 404], (
            f"Unexpected status: {response.status_code}"
        )


@pytest.mark.asyncio
async def test_automation_meeting_with_client_id_header(client: AsyncClient, db_session: AsyncSession):
    """
    Test that adding X-Client-ID header doesn't fix the vulnerability
    (since the endpoint doesn't use it for filtering).
    """
    await setup_two_tenants(db_session)
    tenant_b_data = await create_meeting_with_pv(db_session, CLIENT_B_ID)

    headers = {
        "X-Internal-API-Key": settings.INTERNAL_API_SECRET,
    }

    response = await client.get(
        f"/api/v1/reports/automation/meeting/{tenant_b_data['meeting_id']}?client_id={CLIENT_A_ID}",
        headers=headers,
    )

    if response.status_code == 200:
        pytest.fail(
            f"VULNERABILITY CONFIRMED: X-Client-ID header is ignored!\n"
            f"Status: 200\n"
            f"Meeting data: {response.json()}\n"
            f"VULNERABLE LINE: reports.py:124 - Endpoint doesn't use X-Client-ID for filtering"
        )
    else:
        assert response.status_code in [403, 404], (
            f"Unexpected status: {response.status_code}"
        )


@pytest.mark.asyncio
async def test_automation_invalid_api_key(client: AsyncClient, db_session: AsyncSession):
    """
    Verify that invalid API key is rejected (sanity check).
    """
    await setup_two_tenants(db_session)
    tenant_b_data = await create_meeting_with_pv(db_session, CLIENT_B_ID)

    headers = {
        "X-Internal-API-Key": "invalid-key-12345",
    }

    response = await client.get(
        f"/api/v1/reports/automation/meeting/{tenant_b_data['meeting_id']}",
        headers=headers,
    )

    assert response.status_code == 403, (
        f"Invalid API key should be rejected. Status: {response.status_code}"
    )
