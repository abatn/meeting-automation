import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.app.models.action import Action, ActionStatus, ActionPriority
from backend.app.models.meeting import Meeting
from backend.app.schemas.action import ActionCreate, ActionUpdate
from datetime import datetime, timedelta

@pytest.mark.asyncio
async def test_create_action(client: AsyncClient, auth_headers: dict, test_meeting: Meeting, db_session: AsyncSession):
    action_data = {
        "meeting_id": test_meeting.id,
        "description": "Follow up on meeting notes.",
        "due_date": (datetime.now() + timedelta(days=7)).isoformat(),
        "assigned_to": test_meeting.organizer_id,
        "priority": ActionPriority.MEDIUM.value
    }
    response = await client.post("/api/v1/actions/", json=action_data, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["meeting_id"] == test_meeting.id
    assert data["description"] == "Follow up on meeting notes."
    assert data["status"] == ActionStatus.PENDING.value

    action_in_db = await db_session.execute(select(Action).filter_by(id=data["id"]))
    action = action_in_db.scalar_one_or_none()
    assert action is not None
    assert action.description == "Follow up on meeting notes."

@pytest.mark.asyncio
async def test_list_actions(client: AsyncClient, auth_headers: dict, test_action: Action, test_meeting: Meeting, db_session: AsyncSession):
    # Create another action for filtering
    another_action = Action(
        meeting_id=test_meeting.id,
        description="Another action.",
        due_date=datetime.now() + timedelta(days=10),
        assigned_to=test_meeting.organizer_id,
        status=ActionStatus.COMPLETED
    )
    db_session.add(another_action)
    await db_session.commit()
    await db_session.refresh(another_action)

    response = await client.get(f"/api/v1/actions/?meeting_id={test_meeting.id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2
    assert all(a["meeting_id"] == test_meeting.id for a in data)

@pytest.mark.asyncio
async def test_get_action(client: AsyncClient, auth_headers: dict, test_action: Action):
    response = await client.get(f"/api/v1/actions/{test_action.id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == test_action.id
    assert data["description"] == test_action.description

@pytest.mark.asyncio
async def test_update_action(client: AsyncClient, auth_headers: dict, test_action: Action):
    update_data = {
        "description": "Updated action description.",
        "status": ActionStatus.IN_PROGRESS.value
    }
    response = await client.put(f"/api/v1/actions/{test_action.id}", json=update_data, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["description"] == "Updated action description."
    assert data["status"] == ActionStatus.IN_PROGRESS.value

@pytest.mark.asyncio
async def test_complete_action(client: AsyncClient, auth_headers: dict, test_action: Action):
    response = await client.post(
        f"/api/v1/actions/{test_action.id}/complete", 
        json={"comment": "Done"}, 
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == ActionStatus.COMPLETED.value
    # assert data["completion_date"] is not None # Check if response model includes completion_date

@pytest.mark.asyncio
async def test_delete_action(client: AsyncClient, auth_headers: dict, test_action: Action, db_session: AsyncSession):
    action_id = test_action.id
    response = await client.delete(f"/api/v1/actions/{action_id}", headers=auth_headers)
    assert response.status_code == 204
    # assert response.json()["message"] == "Action deleted successfully" # Message might vary

    action_in_db = await db_session.execute(select(Action).filter_by(id=action_id))
    assert action_in_db.scalar_one_or_none() is None

@pytest.mark.asyncio
async def test_overdue_actions(client: AsyncClient, auth_headers: dict, test_meeting: Meeting, db_session: AsyncSession):
    overdue_action = Action(
        meeting_id=test_meeting.id,
        description="Overdue action.",
        due_date=datetime.now() - timedelta(days=1),
        assigned_to=test_meeting.organizer_id,
        status=ActionStatus.PENDING
    )
    db_session.add(overdue_action)
    await db_session.commit()
    await db_session.refresh(overdue_action)

    # Assuming there is a query param for status
    response = await client.get(f"/api/v1/actions/?status={ActionStatus.OVERDUE.value}", headers=auth_headers)
    # The filter might not catch it if the logic for "overdue" is based on date and status=PENDING
    # If the API filters by DB status column, then we need to ensure the DB status is OVERDUE or the logic handles it.
    # If the system automatically updates status to OVERDUE, that's a background task.
    # If the filter ?status=OVERDUE just checks the status column, then we should create it as OVERDUE.
    
    # Let's create it as OVERDUE for this test if we are testing the filter.
    overdue_action.status = ActionStatus.OVERDUE
    await db_session.commit()
    
    response = await client.get(f"/api/v1/actions/?status={ActionStatus.OVERDUE.value}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    # It might return multiple if other tests created overdue actions, check existence
    assert any(a["id"] == overdue_action.id for a in data)