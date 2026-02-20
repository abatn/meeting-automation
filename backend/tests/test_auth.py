from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

def test_signup(client: TestClient) -> None:
    data = {
        "email": "test@example.com",
        "password": "testpassword",
        "full_name": "Test User",
        "role": "participant",
        "department": "IT"
    }
    response = client.post("/api/v1/auth/signup", json=data)
    assert response.status_code == 200
    content = response.json()
    assert content["email"] == data["email"]
    assert "id" in content

def test_login(client: TestClient) -> None:
    login_data = {
        "username": "test@example.com",
        "password": "testpassword"
    }
    response = client.post("/api/v1/auth/login/access-token", data=login_data)
    assert response.status_code == 200
    content = response.json()
    assert "access_token" in content
    assert content["token_type"] == "bearer"