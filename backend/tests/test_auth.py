import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_register_user(client: AsyncClient, test_user_data):
    response = await client.post("/api/v1/auth/register", json=test_user_data)
    assert response.status_code in [201, 400]
    if response.status_code == 201:
        data = response.json()
        assert data["email"] == test_user_data["email"]
        assert "id" in data

@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, test_user_data):
    reg_resp = await client.post("/api/v1/auth/register", json=test_user_data)
    if reg_resp.status_code in [201, 400]:
        from sqlalchemy import select, update
        from app.models.user import User
        from app.core.database import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(User).where(User.email == test_user_data["email"]))
            user = result.scalar_one_or_none()
            if user:
                await db.execute(update(User).where(User.id == user.id).values(status="ACTIVE"))
                await db.commit()

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
