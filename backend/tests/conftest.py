import pytest
import pytest_asyncio
import asyncio
from typing import Generator
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.core.database import Base, get_db
from app.core.config import settings

# Test Database URL (In-Memory SQLite für schnellere Tests)
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestingSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Event loop policy (fixes pytest-asyncio DeprecationWarning)
@pytest.fixture(scope="session")
def event_loop_policy():
    return asyncio.get_event_loop_policy()

@pytest_asyncio.fixture(scope="function")
async def db_session() -> Generator:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with TestingSessionLocal() as session:
        yield session
        
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

from app.api import deps
from app.models.user import User as UserModel, UserStatus
from unittest.mock import patch, MagicMock

@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> Generator:
    async def override_get_db():
        yield db_session
        
    async def override_get_current_user():
        return UserModel(
            id="test-user-id",
            client_id="test-client-id",
            email="dg@example.com",
            full_name="Test DG",
            status=UserStatus.ACTIVE.value,
            is_superuser=True
        )
    
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[deps.get_current_user] = override_get_current_user
    
    with patch('app.middleware.audit_middleware.AsyncSessionLocal', return_value=TestingSessionLocal()), \
         patch('boto3.client') as mock_boto, \
         patch('celery.app.base.Celery.send_task') as mock_celery:
        async with AsyncClient(app=app, base_url="http://test") as ac:
            yield ac
            
    app.dependency_overrides.clear()

@pytest.fixture
def normal_user_token_headers():
    return {"Authorization": "Bearer fake-token"}

@pytest.fixture
def test_user_data():
    return {
        "email": "dg@example.com",
        "password": "StrongPassword123!",
        "full_name": "Test DG",
        "role": "DG"
    }

@pytest.fixture
def test_meeting_data():
    return {
        "title": "Strategy Meeting 2026",
        "description": "Annual strategy review",
        "start_time": "2026-03-01T10:00:00",
        "end_time": "2026-03-01T11:00:00",
        "location": "Tunis Office",
        "participants": []
    }
