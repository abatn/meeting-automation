from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

def test_create_meeting(client: TestClient) -> None:
    # First login to get token
    login_data = {
        "username": "test@example.com",
        "password": "testpassword"
    }
    login_response = client.post("/api/v1/auth/login/access-token", data=login_data)
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create meeting
    meeting_data = {
        "title": "Test Meeting",
        "description": "Test Description",
        "location": "Test Room",
        "start_time": datetime.utcnow().isoformat(),
        "end_time": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
        "status": "scheduled"
    }
    response = client.post("/api/v1/meetings/", json=meeting_data, headers=headers)
    assert response.status_code == 200
    content = response.json()
    assert content["title"] == meeting_data["title"]
    assert "id" in content

def test_read_meetings(client: TestClient) -> None:
    login_data = {
        "username": "test@example.com",
        "password": "testpassword"
    }
    login_response = client.post("/api/v1/auth/login/access-token", data=login_data)
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/api/v1/meetings/", headers=headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)