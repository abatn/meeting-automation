import pytest
from httpx import AsyncClient
from sqlalchemy import select
from app.models.audit_log import AuditLog
from sqlalchemy.ext.asyncio import AsyncSession

@pytest.mark.asyncio
async def test_audit_log_creation(client: AsyncClient, db_session: AsyncSession, normal_user_token_headers):
    # Eine Aktion ausführen, die geloggt werden sollte (z.B. Meeting erstellen)
    meeting_data = {
        "title": "Audit Test Meeting",
        "start_time": "2026-03-01T10:00:00",
        "end_time": "2026-03-01T11:00:00"
    }
    
    await client.post(
        "/api/v1/meetings/",
        json=meeting_data
    )
    
    # Prüfen, ob ein Audit-Log Eintrag erstellt wurde
    result = await db_session.execute(select(AuditLog).order_by(AuditLog.id.desc()))
    audit_entry = result.scalars().first()
    
    assert audit_entry is not None
    assert audit_entry.action in ["POST", "ACTION_ASSIGNED_EXTERNAL", "CREATE_MEETING"]

@pytest.mark.asyncio
async def test_audit_log_immutability(client: AsyncClient, normal_user_token_headers):
    # Versuchen, Audit-Logs über die API zu löschen (sollte nicht existieren oder verboten sein)
    response = await client.delete("/api/v1/audit-logs/1", headers=normal_user_token_headers)
    assert response.status_code in [404, 405, 403]