import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.models.user import User, UserRole
from backend.app.schemas.user import UserCreate, UserUpdate
from http import HTTPStatus
from backend.app.core.security import create_access_token_for_user, verify_password, get_password_hash
from backend.app.core.config import settings
from datetime import timedelta

@pytest.mark.asyncio
async def test_create_user(client: AsyncClient, db_session: AsyncSession):
    response = await client.post(
        "/api/v1/users/",
        json={
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "newpassword",
            "full_name": "New User",
            "role": "participant"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "newuser"
    assert data["email"] == "newuser@example.com"
    assert data["full_name"] == "New User"
    assert data["role"] == "participant"
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data

    # Verify user in DB
    user = await db_session.get(User, data["id"])
    assert user is not None
    assert user.username == "newuser"
    assert verify_password("newpassword", user.hashed_password)

@pytest.mark.asyncio
async def test_create_user_duplicate_email(client: AsyncClient, test_user: User):
    response = await client.post(
        "/api/v1/users/",
        json={
            "username": "anotheruser",
            "email": test_user.email,  # Duplicate email
            "password": "anotherpassword",
            "full_name": "Another User",
            "role": "participant"
        }
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "Email already registered"}

@pytest.mark.asyncio
async def test_create_user_duplicate_username(client: AsyncClient, test_user: User):
    response = await client.post(
        "/api/v1/users/",
        json={
            "username": test_user.username,  # Duplicate username
            "email": "another@example.com",
            "password": "anotherpassword",
            "full_name": "Another User",
            "role": "participant"
        }
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "Username already registered"}

@pytest.mark.asyncio
async def test_read_users_me(client: AsyncClient, test_user: User, auth_headers: dict):
    response = await client.get("/api/v1/users/me", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == test_user.username
    assert data["email"] == test_user.email

@pytest.mark.asyncio
async def test_read_users_me_unauthenticated(client: AsyncClient):
    response = await client.get("/api/v1/users/me")
    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}

@pytest.mark.asyncio
async def test_authenticate_user(client: AsyncClient, test_user: User):
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": test_user.email, "password": "testpassword"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

@pytest.mark.asyncio
async def test_authenticate_user_bad_password(client: AsyncClient, test_user: User):
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": test_user.email, "password": "wrongpassword"}
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Incorrect username or password"}

@pytest.mark.asyncio
async def test_authenticate_user_bad_username(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "nonexistent@example.com", "password": "testpassword"}
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Incorrect username or password"}

@pytest.mark.asyncio
async def test_authenticate_user_missing_credentials(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "", "password": ""}
    )
    assert response.status_code == 422
    # Verify that the response contains validation errors
    assert "detail" in response.json()
    assert isinstance(response.json()["detail"], list)

    response = await client.post(
        "/api/v1/auth/login",
        data={"password": "testpassword"}
    )
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "test@example.com"}
    )
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

@pytest.mark.asyncio
async def test_get_current_active_user(client: AsyncClient, test_user: User, auth_headers: dict):
    response = await client.get("/api/v1/users/me", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == test_user.email

@pytest.mark.asyncio
async def test_get_current_active_user_inactive(client: AsyncClient, db_session: AsyncSession, test_user: User):
    test_user.is_active = False
    db_session.add(test_user)
    await db_session.commit()
    await db_session.refresh(test_user)

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token = create_access_token_for_user(
        user_id=test_user.id, expires_delta=access_token_expires
    )
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get("/api/v1/users/me", headers=headers)
    assert response.status_code == 400
    assert response.json() == {"detail": "Inactive user"}

@pytest.mark.asyncio
async def test_get_current_active_superuser(client: AsyncClient, test_admin: User, admin_headers: dict):
    response = await client.get("/api/v1/users/me", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == test_admin.email
    assert data["is_superuser"] is True

@pytest.mark.asyncio
async def test_update_user_me(client: AsyncClient, test_user: User, auth_headers: dict):
    response = await client.put(
        "/api/v1/users/me",
        headers=auth_headers,
        json={"full_name": "Updated Name", "email": "updated@example.com"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["full_name"] == "Updated Name"
    assert data["email"] == "updated@example.com"

    user = await client.get("/api/v1/users/me", headers=auth_headers)
    assert user.json()["full_name"] == "Updated Name"
    assert user.json()["email"] == "updated@example.com"

@pytest.mark.asyncio
async def test_update_user_me_password(client: AsyncClient, test_user: User, auth_headers: dict):
    response = await client.put(
        "/api/v1/users/me",
        headers=auth_headers,
        json={"password": "newtestpassword"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == test_user.username

    # Try to authenticate with new password
    auth_response = await client.post(
        "/api/v1/auth/login",
        data={"username": test_user.email, "password": "newtestpassword"}
    )
    assert auth_response.status_code == 200

@pytest.mark.asyncio
async def test_update_user_me_duplicate_email(client: AsyncClient, db_session: AsyncSession, test_user: User, test_admin: User, auth_headers: dict):
    response = await client.put(
        "/api/v1/users/me",
        headers=auth_headers,
        json={"email": test_admin.email}  # Duplicate email
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "Email already registered"}

@pytest.mark.asyncio
async def test_update_user_me_duplicate_username(client: AsyncClient, db_session: AsyncSession, test_user: User, test_admin: User, auth_headers: dict):
    response = await client.put(
        "/api/v1/users/me",
        headers=auth_headers,
        json={"username": test_admin.username}  # Duplicate username
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "Username already registered"}

@pytest.mark.asyncio
async def test_read_users(client: AsyncClient, test_admin: User, admin_headers: dict):
    response = await client.get("/api/v1/users/", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert any(user["email"] == test_admin.email for user in data)

@pytest.mark.asyncio
async def test_read_users_unauthorized(client: AsyncClient, auth_headers: dict):
    response = await client.get("/api/v1/users/", headers=auth_headers)
    assert response.status_code == 403
    assert response.json() == {"detail": "Role admin required"}

@pytest.mark.asyncio
async def test_read_user_by_id(client: AsyncClient, test_user: User, test_admin: User, admin_headers: dict):
    response = await client.get(f"/api/v1/users/{test_user.id}", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == test_user.email

@pytest.mark.asyncio
async def test_read_user_by_id_not_found(client: AsyncClient, admin_headers: dict):
    response = await client.get("/api/v1/users/99999", headers=admin_headers)
    assert response.status_code == 404
    assert response.json() == {"detail": "User not found"}

@pytest.mark.asyncio
async def test_update_user_by_id(client: AsyncClient, test_user: User, test_admin: User, admin_headers: dict):
    response = await client.put(
        f"/api/v1/users/{test_user.id}",
        headers=admin_headers,
        json={"full_name": "Admin Updated User", "role": "admin"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["full_name"] == "Admin Updated User"
    assert data["role"] == "admin"

    user = await client.get(f"/api/v1/users/{test_user.id}", headers=admin_headers)
    assert user.json()["full_name"] == "Admin Updated User"
    assert user.json()["role"] == "admin"

@pytest.mark.asyncio
async def test_update_user_by_id_unauthorized(client: AsyncClient, test_user: User, auth_headers: dict):
    response = await client.put(
        f"/api/v1/users/{test_user.id}",
        headers=auth_headers,
        json={"full_name": "Unauthorized Update"}
    )
    assert response.status_code == 403
    assert response.json() == {"detail": "Role admin required"}

@pytest.mark.asyncio
async def test_delete_user_by_id(client: AsyncClient, db_session: AsyncSession, test_user: User, test_admin: User, admin_headers: dict):
    user_to_delete = User(
        username="todelete",
        email="todelete@example.com",
        hashed_password=get_password_hash("deletepass"),
        full_name="To Delete",
        role=UserRole.PARTICIPANT
    )
    db_session.add(user_to_delete)
    await db_session.commit()
    await db_session.refresh(user_to_delete)

    response = await client.delete(f"/api/v1/users/{user_to_delete.id}", headers=admin_headers)
    assert response.status_code == 200
    assert response.json() == {"message": "User deleted successfully"}

    user_in_db = await db_session.get(User, user_to_delete.id)
    assert user_in_db is None

@pytest.mark.asyncio
async def test_delete_user_by_id_unauthorized(client: AsyncClient, test_user: User, auth_headers: dict):
    response = await client.delete(f"/api/v1/users/{test_user.id}", headers=auth_headers)
    assert response.status_code == 403
    assert response.json() == {"detail": "Role admin required"}

@pytest.mark.asyncio
async def test_delete_user_by_id_not_found(client: AsyncClient, admin_headers: dict):
    response = await client.delete("/api/v1/users/99999", headers=admin_headers)
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json() == {"detail": "User not found"}