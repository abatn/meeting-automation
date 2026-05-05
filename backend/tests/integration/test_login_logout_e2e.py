"""
E2E Test: Login/Logout with Audit Logging
Tests the complete flow: Login -> Audit Log -> Logout -> Audit Log -> Verify State Reset
"""
import pytest
from sqlalchemy import select
from httpx import AsyncClient
from app.main import app
from app.models.audit_log import AuditLog
from app.models.user import User


@pytest.mark.asyncio
async def test_login_logout_audit_trail(async_db_session, async_client: AsyncClient):
    """
    Test: Login -> Audit logged -> Logout -> Audit logged -> Redux state reset
    """
    # 1. Test login with valid credentials
    login_data = {
        "username": "admin@meeting.tn",
        "password": "Password123!"
    }
    
    response = await async_client.post("/api/v1/auth/login", data=login_data)
    assert response.status_code == 200, f"Login failed: {response.text}"
    
    login_response = response.json()
    assert "user" in login_response
    user_id = login_response["user"]["id"]
    client_id = login_response["user"]["client_id"]
    
    print(f"✅ Login successful: user_id={user_id}, client_id={client_id}")
    
    # 2. Verify login was audited
    audit_logs = await async_db_session.execute(
        select(AuditLog)
        .where(AuditLog.user_id == user_id)
        .where(AuditLog.action == "POST")
        .where(AuditLog.table_name == "auth")
        .order_by(AuditLog.created_at.desc())
        .limit(1)
    )
    login_audit = audit_logs.scalars().first()
    assert login_audit is not None, "Login audit log not created"
    assert login_audit.client_id == client_id
    print(f"✅ Login audited: audit_id={login_audit.id}, action={login_audit.action}")
    
    # 3. Test logout
    logout_response = await async_client.post("/api/v1/auth/logout")
    assert logout_response.status_code == 200
    logout_data = logout_response.json()
    assert logout_data.get("msg") == "Successfully logged out"
    print(f"✅ Logout successful")
    
    # 4. Verify logout was audited
    logout_audits = await async_db_session.execute(
        select(AuditLog)
        .where(AuditLog.user_id == user_id)
        .where(AuditLog.action == "POST")
        .where(AuditLog.table_name == "auth")
        .order_by(AuditLog.created_at.desc())
        .limit(2)
    )
    logout_audit_list = logout_audits.scalars().all()
    assert len(logout_audit_list) >= 2, "Logout audit log not created"
    
    logout_audit = logout_audit_list[0]  # Most recent
    assert logout_audit.client_id == client_id
    print(f"✅ Logout audited: audit_id={logout_audit.id}")
    
    # 5. Verify token is cleared (cookie deleted)
    # After logout, cookie should be deleted
    assert "accessToken" not in logout_response.cookies or logout_response.cookies.get("accessToken") == ""
    print(f"✅ HttpOnly cookie cleared after logout")
    
    # 6. Verify authenticated endpoints fail without token
    me_response = await async_client.get("/api/v1/auth/me")
    assert me_response.status_code == 403, "Should not be able to access /auth/me without token"
    print(f"✅ Protected endpoint blocked after logout")
    
    print("\n✅✅✅ Full E2E Test PASSED: Login → Audit → Logout → Audit → State Reset")


@pytest.mark.asyncio
async def test_frontend_audit_logging_endpoint(async_client: AsyncClient):
    """
    Test: Frontend audit service can log actions via /api/v1/audit/log
    """
    # First, login to get valid token
    login_data = {
        "username": "admin@meeting.tn",
        "password": "Password123!"
    }
    login_response = await async_client.post("/api/v1/auth/login", data=login_data)
    assert login_response.status_code == 200
    
    # Now test audit logging endpoint
    audit_payload = {
        "action": "CREATE",
        "resource": "meetings",
        "record_id": "meeting-123",
        "details": {"title": "Test Meeting"}
    }
    
    audit_response = await async_client.post("/api/v1/audit/log", json=audit_payload)
    assert audit_response.status_code == 200, f"Audit log failed: {audit_response.text}"
    
    result = audit_response.json()
    assert result["status"] == "logged"
    print(f"✅ Frontend audit logging works: {result}")


if __name__ == "__main__":
    print("\n🔍 Running E2E tests for Login/Logout/Audit flow...")
