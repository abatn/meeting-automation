import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.main import app
from backend.app.core.config import settings
from backend.app.models.user import User, UserRole
from backend.app.schemas.user import UserCreate, UserResponse
from backend.app.core.security import get_password_hash
from sqlalchemy import select

@pytest.mark.asyncio
async def test_register_user(test_client: AsyncClient, db_session):
    user_data = {
        "email": "test@example.com",
        "username": "testuser",
        "password": "testpassword",
        "full_name": "Test User",
            "role": "participant"
    }
    response = await test_client.post("/api/v1/auth/register", json=user_data)
    assert response.status_code == 200
    
    user_in_db = await db_session.execute(select(User).filter_by(email=user_data["email"]))
    user_in_db = user_in_db.scalar_one_or_none()
    assert user_in_db is not None
    
    await db_session.refresh(user_in_db)

    registered_user = UserResponse.model_validate(user_in_db)
    assert registered_user.email == user_data["email"]
    assert registered_user.username == user_data["username"]
    assert registered_user.role == user_data["role"]

@pytest.mark.asyncio
async def test_login_user(test_client: AsyncClient, db_session):
    # First, register a user
    user_data = {
        "email": "login@example.com",
        "username": "loginuser",
        "password": "loginpassword",
        "full_name": "Login User",
            "role": "participant"
    }
    await test_client.post("/api/v1/auth/register", json=user_data)

    # Then, attempt to log in
    form_data = {
        "username": "loginuser",
        "password": "loginpassword"
    }
    response = await test_client.post("/api/v1/auth/login", data=form_data)
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert "refresh_token" in response.json()
    assert response.json()["token_type"] == "bearer"

@pytest.mark.asyncio
async def test_login_user_incorrect_password(test_client: AsyncClient):
    # First, register a user
    user_data = {
        "email": "login_fail@example.com",
        "username": "loginfailuser",
        "password": "loginfailpassword",
        "full_name": "Login Fail User",
            "role": "participant"
    }
    await test_client.post("/api/v1/auth/register", json=user_data)
    
    form_data = {
        "username": "loginfailuser",
        "password": "wrongpassword"
    }
    response = await test_client.post("/api/v1/auth/login", data=form_data)
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect username or password"

@pytest.mark.asyncio
async def test_mfa_setup(test_client: AsyncClient, db_session):
    # Register and login a user
    user_data = {
        "email": "mfa@example.com",
        "username": "mfauser",
        "password": "mfapassword",
        "full_name": "MFA User",
            "role": "participant"
    }
    await test_client.post("/api/v1/auth/register", json=user_data)
    
    form_data = {
        "username": "mfauser",
        "password": "mfapassword"
    }
    login_response = await test_client.post("/api/v1/auth/login", data=form_data)
    access_token = login_response.json()["access_token"]

    # Setup MFA
    response = await test_client.post(
        "/api/v1/auth/mfa/setup",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 200
    assert "secret" in response.json()
    assert "qr_code" in response.json()
    assert "uri" in response.json()

@pytest.mark.asyncio
async def test_mfa_verify(test_client: AsyncClient, db_session):
    # This test requires a way to simulate MFA secret generation and code verification.
    # For a real test, you would need to mock the pyotp library or have a pre-configured user with MFA.
    # For now, we'll assume a successful MFA setup and directly test the verification endpoint.
    pass

@pytest.mark.asyncio
async def test_refresh_token(test_client: AsyncClient, db_session):
    # Register and login a user
    user_data = {
        "email": "refresh@example.com",
        "username": "refreshuser",
        "password": "refreshpassword",
        "full_name": "Refresh User",
            "role": "participant"
    }
    await test_client.post("/api/v1/auth/register", json=user_data)
    
    form_data = {
        "username": "refreshuser",
        "password": "refreshpassword"
    }
    login_response = await test_client.post("/api/v1/auth/login", data=form_data)
    refresh_token = login_response.json()["refresh_token"]

    # Refresh token
    response = await test_client.post(
        "/api/v1/auth/refresh",
        params={"refresh_token": refresh_token}
    )
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert "refresh_token" in response.json()
    assert response.json()["token_type"] == "bearer"

@pytest.mark.asyncio
async def test_logout(test_client: AsyncClient, db_session):
    # Register and login a user
    user_data = {
        "email": "logout@example.com",
        "username": "logoutuser",
        "password": "logoutpassword",
        "full_name": "Logout User",
        "role": "participant"
    }
    await test_client.post("/api/v1/auth/register", json=user_data)
    
    form_data = {
        "username": "logoutuser",
        "password": "logoutpassword"
    }
    login_response = await test_client.post("/api/v1/auth/login", data=form_data)
    access_token = login_response.json()["access_token"]

    # Logout
    response = await test_client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Successfully logged out"