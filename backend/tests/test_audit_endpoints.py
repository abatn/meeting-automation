import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta, timezone

from backend.app.models.user import User, UserRole
from backend.app.models.audit_log import AuditLog
from backend.app.schemas.audit import AuditLogCreate
from backend.app.core.security import get_password_hash, create_access_token_for_user
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
async def test_admin_user(db_session: AsyncSession) -> User:
    return await create_test_user(db_session, "audit_admin", "audit_admin@example.com", UserRole.ADMIN)

@pytest_asyncio.fixture
async def test_participant_user(db_session: AsyncSession) -> User:
    return await create_test_user(db_session, "audit_participant", "audit_participant@example.com", UserRole.PARTICIPANT)

@pytest_asyncio.fixture
async def test_audit_log(db_session: AsyncSession, test_admin_user: User) -> AuditLog:
    audit_log = AuditLog(
        user_id=test_admin_user.id,
        action="USER_LOGIN",
        method="POST",
        path="/api/v1/auth/login",
        resource_type="User",
        resource_id=test_admin_user.id,
        details={"message": "User logged in successfully"},
        timestamp=datetime.now(timezone.utc)
    )
    db_session.add(audit_log)
    await db_session.commit()
    await db_session.refresh(audit_log)
    return audit_log

@pytest.mark.asyncio
async def test_get_audit_logs_as_admin(client: AsyncClient, db_session: AsyncSession, test_admin_user: User, test_audit_log: AuditLog):
    token = await get_user_token(test_admin_user)
    response = await client.get(
        "/api/v1/audit/",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert any(log["id"] == test_audit_log.id for log in data)

@pytest.mark.asyncio
async def test_get_audit_logs_as_participant_forbidden(client: AsyncClient, db_session: AsyncSession, test_participant_user: User):
    token = await get_user_token(test_participant_user)
    response = await client.get(
        "/api/v1/audit/",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403
    assert "Not enough permissions" in response.json()["detail"]

@pytest.mark.asyncio
async def test_get_audit_log_by_id_as_admin(client: AsyncClient, db_session: AsyncSession, test_admin_user: User, test_audit_log: AuditLog):
    token = await get_user_token(test_admin_user)
    response = await client.get(
        f"/api/v1/audit/{test_audit_log.id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == test_audit_log.id
    assert data["action"] == test_audit_log.action

@pytest.mark.asyncio
async def test_get_audit_log_by_id_as_participant_forbidden(client: AsyncClient, db_session: AsyncSession, test_participant_user: User, test_audit_log: AuditLog):
    token = await get_user_token(test_participant_user)
    response = await client.get(
        f"/api/v1/audit/{test_audit_log.id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403
    assert "Not enough permissions" in response.json()["detail"]

@pytest.mark.asyncio
async def test_get_audit_logs_filter_by_user_id(client: AsyncClient, db_session: AsyncSession, test_admin_user: User, test_audit_log: AuditLog):
    token = await get_user_token(test_admin_user)
    response = await client.get(
        f"/api/v1/audit/?user_id={test_admin_user.id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert all(log["user_id"] == test_admin_user.id for log in data)
    assert any(log["id"] == test_audit_log.id for log in data)

@pytest.mark.asyncio
async def test_get_audit_logs_filter_by_event_type(client: AsyncClient, db_session: AsyncSession, test_admin_user: User, test_audit_log: AuditLog):
    token = await get_user_token(test_admin_user)
    response = await client.get(
        f"/api/v1/audit/?event_type={test_audit_log.action}",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert all(log["action"] == test_audit_log.action for log in data)
    assert any(log["id"] == test_audit_log.id for log in data)

@pytest.mark.asyncio
async def test_get_audit_logs_filter_by_resource_type(client: AsyncClient, db_session: AsyncSession, test_admin_user: User, test_audit_log: AuditLog):
    token = await get_user_token(test_admin_user)
    response = await client.get(
        f"/api/v1/audit/?resource_type={test_audit_log.resource_type}",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert all(log["resource_type"] == test_audit_log.resource_type for log in data)
    assert any(log["id"] == test_audit_log.id for log in data)

@pytest.mark.asyncio
async def test_get_audit_logs_filter_by_date_range(client: AsyncClient, db_session: AsyncSession, test_admin_user: User, test_audit_log: AuditLog):
    token = await get_user_token(test_admin_user)
    start_date = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    end_date = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    response = await client.get(
        f"/api/v1/audit/?start_date={start_date}&end_date={end_date}",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert any(log["id"] == test_audit_log.id for log in data)
