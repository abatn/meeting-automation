import pytest
from httpx import AsyncClient
from unittest.mock import patch, AsyncMock

@pytest.mark.asyncio
async def test_register_user(client: AsyncClient, test_user_data):
    response = await client.post("/api/v1/auth/register", json=test_user_data)
    assert response.status_code in [201, 400]
    if response.status_code == 201:
        data = response.json()
        assert data["email"] == test_user_data["email"]
        assert "id" in data

@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, test_user_data, db_session):
    # Mock the Celery task to prevent RabbitMQ connection attempts
    with patch("app.tasks.email_tasks.send_invitation_email.delay", new_callable=AsyncMock):
        reg_resp = await client.post("/api/v1/auth/register", json=test_user_data)

    # Use the test's db_session (which has correct DB binding) instead of AsyncSessionLocal
    from sqlalchemy import select, update
    from app.models.user import User

    result = await db_session.execute(select(User).where(User.email == test_user_data["email"]))
    user = result.scalar_one_or_none()
    if user:
        await db_session.execute(update(User).where(User.id == user.id).values(status="ACTIVE"))
        await db_session.commit()

    response = await client.post("/api/v1/auth/login", data={
        "username": test_user_data["email"],
        "password": test_user_data["password"]
    })
    assert response.status_code == 200
    data = response.json()
    assert data["token_type"] == "bearer"
    assert "accessToken" in response.cookies, "Login should set accessToken cookie"

@pytest.mark.asyncio
async def test_login_failed_wrong_password(client: AsyncClient, test_user_data, db_session):
    # Mock Celery task and rate limiter to prevent external dependencies
    with patch("app.tasks.email_tasks.send_invitation_email.delay", new_callable=AsyncMock):
        await client.post("/api/v1/auth/register", json=test_user_data)

    # Activate user first using db_session
    from sqlalchemy import select, update
    from app.models.user import User

    result = await db_session.execute(select(User).where(User.email == test_user_data["email"]))
    user = result.scalar_one_or_none()
    if user:
        await db_session.execute(update(User).where(User.id == user.id).values(status="ACTIVE"))
        await db_session.commit()

    response = await client.post("/api/v1/auth/login", data={
        "username": test_user_data["email"],
        "password": "wrongpassword"
    })
    assert response.status_code == 401, f"Expected 401, got {response.status_code}"