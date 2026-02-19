import pytest
from httpx import AsyncClient
from backend.app.models.meeting import Meeting
from backend.app.models.user import User
from backend.app.models.action import Action
from datetime import datetime, timedelta

@pytest.mark.asyncio
async def test_dg_dashboard_as_dg(client: AsyncClient, admin_headers: dict, test_meeting: Meeting, test_user: User, db_session):
    # Create some meetings and actions for the DG dashboard
    meeting1 = Meeting(
        title="DG Meeting 1",
        description="Description 1",
        start_time=datetime.now() - timedelta(days=5),
        end_time=datetime.now() - timedelta(days=4),
        organizer_id=test_user.id,
        participants=[test_user]
    )
    meeting2 = Meeting(
        title="DG Meeting 2",
        description="Description 2",
        start_time=datetime.now() - timedelta(days=2),
        end_time=datetime.now() - timedelta(days=1),
        organizer_id=test_user.id,
        participants=[test_user]
    )
    db_session.add_all([meeting1, meeting2])
    await db_session.commit()
    await db_session.refresh(meeting1)
    await db_session.refresh(meeting2)

    action1 = Action(
        meeting_id=meeting1.id,
        description="DG Action 1",
        due_date=datetime.now() - timedelta(days=1),
        assigned_to_user_id=test_user.id,
        status="OPEN"
    )
    action2 = Action(
        meeting_id=meeting2.id,
        description="DG Action 2",
        due_date=datetime.now() + timedelta(days=5),
        assigned_to_user_id=test_user.id,
        status="COMPLETED"
    )
    db_session.add_all([action1, action2])
    await db_session.commit()
    await db_session.refresh(action1)
    await db_session.refresh(action2)

    response = await client.get("/api/v1/reports/dg-dashboard", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert "total_meetings" in data
    assert "total_actions" in data
    assert "open_actions" in data
    assert "completed_actions" in data
    assert "overdue_actions" in data

@pytest.mark.asyncio
async def test_dg_dashboard_as_user_forbidden(client: AsyncClient, auth_headers: dict):
    response = await client.get("/api/v1/reports/dg-dashboard", headers=auth_headers)
    assert response.status_code == 403

@pytest.mark.asyncio
async def test_manager_dashboard(client: AsyncClient, auth_headers: dict, test_meeting: Meeting, test_user: User, db_session):
    # Create some meetings and actions for the manager dashboard
    meeting1 = Meeting(
        title="Manager Meeting 1",
        description="Description 1",
        start_time=datetime.now() - timedelta(days=5),
        end_time=datetime.now() - timedelta(days=4),
        organizer_id=test_user.id,
        participants=[test_user]
    )
    meeting2 = Meeting(
        title="Manager Meeting 2",
        description="Description 2",
        start_time=datetime.now() - timedelta(days=2),
        end_time=datetime.now() - timedelta(days=1),
        organizer_id=test_user.id,
        participants=[test_user]
    )
    db_session.add_all([meeting1, meeting2])
    await db_session.commit()
    await db_session.refresh(meeting1)
    await db_session.refresh(meeting2)

    action1 = Action(
        meeting_id=meeting1.id,
        description="Manager Action 1",
        due_date=datetime.now() - timedelta(days=1),
        assigned_to_user_id=test_user.id,
        status="OPEN"
    )
    action2 = Action(
        meeting_id=meeting2.id,
        description="Manager Action 2",
        due_date=datetime.now() + timedelta(days=5),
        assigned_to_user_id=test_user.id,
        status="COMPLETED"
    )
    db_session.add_all([action1, action2])
    await db_session.commit()
    await db_session.refresh(action1)
    await db_session.refresh(action2)

    response = await client.get("/api/v1/reports/manager-dashboard", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "total_meetings" in data
    assert "total_actions" in data
    assert "open_actions" in data
    assert "completed_actions" in data
    assert "overdue_actions" in data

@pytest.mark.asyncio
async def test_participant_dashboard(client: AsyncClient, auth_headers: dict, test_meeting: Meeting, test_user: User, db_session):
    # Create some meetings and actions for the participant dashboard
    meeting1 = Meeting(
        title="Participant Meeting 1",
        description="Description 1",
        start_time=datetime.now() - timedelta(days=5),
        end_time=datetime.now() - timedelta(days=4),
        organizer_id=test_user.id,
        participants=[test_user]
    )
    meeting2 = Meeting(
        title="Participant Meeting 2",
        description="Description 2",
        start_time=datetime.now() - timedelta(days=2),
        end_time=datetime.now() - timedelta(days=1),
        organizer_id=test_user.id,
        participants=[test_user]
    )
    db_session.add_all([meeting1, meeting2])
    await db_session.commit()
    await db_session.refresh(meeting1)
    await db_session.refresh(meeting2)

    action1 = Action(
        meeting_id=meeting1.id,
        description="Participant Action 1",
        due_date=datetime.now() - timedelta(days=1),
        assigned_to_user_id=test_user.id,
        status="OPEN"
    )
    action2 = Action(
        meeting_id=meeting2.id,
        description="Participant Action 2",
        due_date=datetime.now() + timedelta(days=5),
        assigned_to_user_id=test_user.id,
        status="COMPLETED"
    )
    db_session.add_all([action1, action2])
    await db_session.commit()
    await db_session.refresh(action1)
    await db_session.refresh(action2)

    response = await client.get("/api/v1/reports/participant-dashboard", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "total_meetings" in data
    assert "total_actions" in data
    assert "open_actions" in data
    assert "completed_actions" in data
    assert "overdue_actions" in data

@pytest.mark.asyncio
async def test_generate_meeting_report(client: AsyncClient, auth_headers: dict, test_meeting: Meeting):
    response = await client.post(f"/api/v1/reports/meeting/{test_meeting.id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "report_id" in data
    assert data["status"] == "PENDING"

@pytest.mark.asyncio
async def test_generate_action_report(client: AsyncClient, auth_headers: dict, test_user: User):
    response = await client.post(f"/api/v1/reports/actions/{test_user.id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "report_id" in data
    assert data["status"] == "PENDING"

@pytest.mark.asyncio
async def test_export_report_as_pdf(client: AsyncClient, auth_headers: dict, test_report):
    response = await client.get(f"/api/v1/reports/{test_report.id}/export/pdf", headers=auth_headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"] == f"attachment; filename=report_{test_report.id}.pdf"

@pytest.mark.asyncio
async def test_export_report_as_excel(client: AsyncClient, auth_headers: dict, test_report):
    response = await client.get(f"/api/v1/reports/{test_report.id}/export/excel", headers=auth_headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert response.headers["content-disposition"] == f"attachment; filename=report_{test_report.id}.xlsx"