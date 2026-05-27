import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_register_user(client: AsyncClient, test_user_data):
    response = await client.post("/api/v1/auth/register", json=test_user_data)
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == test_user_data["email"]
    assert "id" in data

@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, test_user_data):
    # Erst registrieren
    await client.post("/api/v1/auth/register", json=test_user_data)
    
    # Login
    response = await client.post("/api/v1/auth/login", data={
        "username": test_user_data["email"],
        "password": test_user_data["password"]
    })
    assert response.status_code == 200
    data = response.json()
    assert data["token_type"] == "bearer"
    assert "accessToken" in response.cookies, "Login should set accessToken cookie"

@pytest.mark.asyncio
async def test_login_failed_wrong_password(client: AsyncClient, test_user_data):
    await client.post("/api/v1/auth/register", json=test_user_data)
    
    response = await client.post("/api/v1/auth/login", data={
        "username": test_user_data["email"],
        "password": "wrongpassword"
    })
    assert response.status_code == 401
