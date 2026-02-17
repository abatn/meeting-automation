import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import sys
sys.path.insert(0, ".")
from backend.app.main import app
from backend.app.core.config import settings
from backend.app.core.database import Base, get_db, SessionLocal
pytest_plugins = ["pytest_asyncio"]

# Use an in-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite+aiosqlite:///./test.db"

engine = create_async_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession)


@pytest_asyncio.fixture(scope="function")
async def db_session():
    """
    Create a new database session for each test and handle table creation/dropping.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with TestingSessionLocal(bind=engine) as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest_asyncio.fixture(scope="function")
async def test_client(db_session: AsyncSession):
    """
    Create an asynchronous test client for the FastAPI application.
    """
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()
