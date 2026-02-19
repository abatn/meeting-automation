import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.app.models.audit_log import AuditLog
from backend.app.models.user import User
from backend.app.schemas.audit import AuditLogFilter
from datetime import datetime, timedelta

@pytest.mark.asyncio
async def test_audit_log_on_every_api_request(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    initial_audit_logs = await db_session.execute(select(AuditLog))
    initial_count = len(initial_audit_logs.scalars().all())

    response = await client.get("/api/v1/users/me", headers=auth_headers)
    assert response.status_code == 200

    updated_audit_logs = await db_session.execute(select(AuditLog))
    updated_count = len(updated_audit_logs.scalars().all())
    assert updated_count == initial_count + 1

    latest_log = updated_audit_logs.scalars().all()[-1]
    assert latest_log.action == "GET /api/v1/users/me"
    assert latest_log.user_id is not None
    assert latest_log.status_code == 200

@pytest.mark.asyncio
async def test_get_audit_logs_as_admin(client: AsyncClient, admin_headers: dict, db_session: AsyncSession, test_user: User):
    # Create some audit logs
    log1 = AuditLog(
        user_id=test_user.id,
        action="GET /api/v1/meetings",
        method="GET",
        path="/api/v1/meetings",
        resource_type="meeting",
        timestamp=datetime.now() - timedelta(hours=2),
        status_code=200,
        ip_address="127.0.0.1",
        user_agent="test-client"
    )
    log2 = AuditLog(
        user_id=test_user.id,
        action="POST /api/v1/meetings",
        method="POST",
        path="/api/v1/meetings",
        resource_type="meeting",
        timestamp=datetime.now() - timedelta(hours=1),
        status_code=200,
        ip_address="127.0.0.1",
        user_agent="test-client"
    )
    db_session.add_all([log1, log2])
    await db_session.commit()
    await db_session.refresh(log1)
    await db_session.refresh(log2)

    response = await client.get("/api/v1/audit/", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2
    assert any(log["action"] == "GET /api/v1/meetings" for log in data)
    assert any(log["action"] == "POST /api/v1/meetings" for log in data)

@pytest.mark.asyncio
async def test_get_audit_logs_as_user_forbidden(client: AsyncClient, auth_headers: dict):
    response = await client.get("/api/v1/audit/", headers=auth_headers)
    assert response.status_code == 403

@pytest.mark.asyncio
async def test_sensitive_data_masked(client: AsyncClient, db_session: AsyncSession):
    # Simulate a login request with sensitive data
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "testuser", "password": "testpassword"},
        headers={"User-Agent": "test-client"}
    )
    assert response.status_code == 401 # Assuming login fails for non-existent user

    latest_log_query = await db_session.execute(select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(1))
    latest_log = latest_log_query.scalar_one_or_none()

    assert latest_log is not None
    assert latest_log.action == "POST /api/v1/auth/login"
    assert "password" not in latest_log.request_body
    assert "testpassword" not in latest_log.request_body
    assert "username" in latest_log.request_body
    assert "testuser" in latest_log.request_body # Username is not considered sensitive for masking

@pytest.mark.asyncio
async def test_audit_logs_filter(client: AsyncClient, admin_headers: dict, db_session: AsyncSession, test_user: User):
    # Create specific logs for filtering
    log_user_me = AuditLog(
        user_id=test_user.id,
        action="GET /api/v1/users/me",
        method="GET",
        path="/api/v1/users/me",
        resource_type="user",
        timestamp=datetime.now() - timedelta(days=1),
        status_code=200,
        ip_address="192.168.1.1",
        user_agent="filter-client"
    )
    log_post_meeting = AuditLog(
        user_id=test_user.id,
        action="POST /api/v1/meetings",
        method="POST",
        path="/api/v1/meetings",
        resource_type="meeting",
        timestamp=datetime.now() - timedelta(hours=6),
        status_code=201,
        ip_address="192.168.1.2",
        user_agent="filter-client"
    )
    db_session.add_all([log_user_me, log_post_meeting])
    await db_session.commit()
    await db_session.refresh(log_user_me)
    await db_session.refresh(log_post_meeting)

    # Filter by action
    response = await client.get("/api/v1/audit/?event_type=GET%20/api/v1/users/me", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert all(log["action"] == "GET /api/v1/users/me" for log in data)

    # Filter by status code
    response = await client.get("/api/v1/audit/?status_code=201", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert all(log["status_code"] == 201 for log in data)

    # Filter by date range
    start_date = (datetime.now() - timedelta(days=2)).isoformat()
    end_date = (datetime.now() - timedelta(hours=12)).isoformat()
    response = await client.get(f"/api/v1/audit/?start_date={start_date}&end_date={end_date}", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert any(log["action"] == "GET /api/v1/users/me" for log in data)
    assert not any(log["action"] == "POST /api/v1/meetings" for log in data) # Should be excluded by end_date

@pytest.mark.asyncio
async def test_audit_logs_export(client: AsyncClient, admin_headers: dict, db_session: AsyncSession, test_user: User):
    # Create some audit logs for export
    log1 = AuditLog(
        user_id=test_user.id,
        action="GET /api/v1/audit/export",
        method="GET",
        path="/api/v1/audit/export",
        resource_type="audit_log",
        timestamp=datetime.now() - timedelta(minutes=30),
        status_code=200,
        ip_address="127.0.0.1",
        user_agent="test-client"
    )
    db_session.add(log1)
    await db_session.commit()
    await db_session.refresh(log1)

    response = await client.get("/api/v1/audit/export", headers=admin_headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv"
    assert response.headers["content-disposition"] == "attachment; filename=audit_logs.csv"
    assert "action,timestamp,user_id,status_code,ip_address,user_agent" in response.text
    assert "GET /api/v1/audit/export" in response.text
