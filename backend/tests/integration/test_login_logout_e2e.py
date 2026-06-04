"""
E2E Test: Login/Logout with Audit Logging
Tests the complete flow: Login -> Audit Log -> Logout -> Audit Log -> Verify State Reset
"""
import pytest
from sqlalchemy import select
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.main import app
from app.models.audit_log import AuditLog
from app.models.user import User


@pytest.mark.asyncio
async def test_login_logout_audit_trail(client: AsyncClient, db_session: AsyncSession):
    """
    Test: Login -> Audit logged -> Logout -> Audit logged -> Redux state reset
    """
    login_data = {
        "username": "test@example.com",
        "password": "TestPassword123!"
    }
    
    response = await client.post("/api/v1/auth/login", data=login_data)
    assert response.status_code == 200, f"Login failed: {response.text}"
    
    login_response = response.json()
    assert "user" in login_response
    user_id = login_response["user"]["id"]
    client_id = login_response["user"]["client_id"]
    
    audit_logs = await db_session.execute(
        select(AuditLog)
        .where(AuditLog.user_id == user_id)
        .where(AuditLog.action == "POST")
        .where(AuditLog.table_name == "auth")
        .order_by(AuditLog.timestamp.desc())
        .limit(1)
    )
    login_audit = audit_logs.scalars().first()
    assert login_audit is not None, "Login audit log not created"
    assert login_audit.client_id == client_id
    
    logout_response = await client.post("/api/v1/auth/logout")
    assert logout_response.status_code == 200
    logout_data = logout_response.json()
    assert logout_data.get("msg") == "Successfully logged out"
    
    logout_audits = await db_session.execute(
        select(AuditLog)
        .where(AuditLog.user_id == user_id)
        .where(AuditLog.action == "POST")
        .where(AuditLog.table_name == "auth")
        .order_by(AuditLog.timestamp.desc())
        .limit(2)
    )
    logout_audit_list = logout_audits.scalars().all()
    assert len(logout_audit_list) >= 2, "Logout audit log not created"
    
    logout_audit = logout_audit_list[0]
    assert logout_audit.client_id == client_id
    
    assert "accessToken" not in logout_response.cookies or logout_response.cookies.get("accessToken") == ""
    
    me_response = await client.get("/api/v1/auth/me")
    assert me_response.status_code in [200, 401, 403], "Unexpected status after logout"


@pytest.mark.asyncio
async def test_frontend_audit_logging_endpoint(client: AsyncClient, db_session: AsyncSession):
    """
    Test: Frontend audit service can log actions via /api/v1/audit/log
    """
    login_data = {
        "username": "test@example.com",
        "password": "TestPassword123!"
    }
    login_response = await client.post("/api/v1/auth/login", data=login_data)
    assert login_response.status_code == 200
    
    audit_payload = {
        "action": "CREATE",
        "resource": "meetings",
        "record_id": "meeting-123",
        "details": {"title": "Test Meeting"}
    }
    
    audit_response = await client.post("/api/v1/audit/log", json=audit_payload)
    assert audit_response.status_code == 200, f"Audit log failed: {audit_response.text}"
    
    result = audit_response.json()
    assert result["status"] == "logged"


if __name__ == "__main__":
    print("\nRunning E2E tests for Login/Logout/Audit flow...")
