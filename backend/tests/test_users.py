import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.models.user import User, UserRole
from backend.app.core.security import get_password_hash, create_access_token_for_user
from datetime import timedelta
from backend.app.core.config import settings

# Helper function to create a user with a specific role
async def create_test_user(db_session: AsyncSession, username: str, email: str, role: UserRole):
    password = "pw"
    hashed_password = get_password_hash(password)
    user = User(
        username=username,
        email=email,
        hashed_password=hashed_password,
        full_name=f"{username} Full Name",
        role=role,
        is_active=True,
        is_superuser=False
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user

# Helper function to get a token for a user
async def get_user_token(user: User):
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return create_access_token_for_user(
        user_id=user.id, expires_delta=access_token_expires
    )

@pytest_asyncio.fixture
async def test_user_users_endpoint(db_session: AsyncSession) -> User:
    return await create_test_user(db_session, "testuser_users", "testuser_users@example.com", UserRole.PARTICIPANT)

@pytest.mark.asyncio
async def test_read_users_me(client: AsyncClient, db_session: AsyncSession, test_user_users_endpoint: User):
    token = await get_user_token(test_user_users_endpoint)
    response = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == test_user_users_endpoint.username
    assert data["email"] == test_user_users_endpoint.email
    assert data["full_name"] == test_user_users_endpoint.full_name
    assert data["role"] == test_user_users_endpoint.role.value