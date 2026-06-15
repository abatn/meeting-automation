import pytest
from httpx import AsyncClient
from sqlalchemy import select
from app.models.audit_log import AuditLog
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import AsyncSessionLocal

@pytest.mark.asyncio
async def test_audit_log_creation(client: AsyncClient, db_session: AsyncSession, normal_user_token_headers):
    # Eine Aktion ausführen, die geloggt werden sollte (z.B. Meeting erstellen)
    meeting_data = {
        "title": "Audit Test Meeting",
        "start_time": "2026-03-01T10:00:00",
        "end_time": "2026-03-01T11:00:00"
    }
    
    response = await client.post(
        "/api/v1/meetings/",
        json=meeting_data
    )
    assert response.status_code == 201, f"Expected 201, got {response.status_code}"
    
    # AuditMiddleware uses AsyncSessionLocal (not the test's db_session)
    # Must query with the same session to see the audit log entry
    async with AsyncSessionLocal() as audit_session:
        result = await audit_session.execute(
            select(AuditLog)
            .where(AuditLog.table_name == "meetings")
            .order_by(AuditLog.id.desc())
        )
        audit_entry = result.scalars().first()
    
    assert audit_entry is not None
    assert audit_entry.action in ["POST", "ACTION_ASSIGNED_EXTERNAL", "CREATE_MEETING"]

@pytest.mark.asyncio
async def test_audit_log_immutability(client: AsyncClient, normal_user_token_headers):
    # Versuchen, Audit-Logs über die API zu löschen (sollte nicht existieren oder verboten sein)
    response = await client.delete("/api/v1/audit-logs/1", headers=normal_user_token_headers)
    assert response.status_code in [404, 405, 403]