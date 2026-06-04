from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings
from starlette.requests import Request
import os

# Create Async Engine
# ISO 27001: Ensure connection string is loaded from secure environment variables
# For E2E tests, use NullPool to avoid asyncpg enum OID caching issues after schema resets
pool_class = None
if os.getenv("E2E_TEST", "").lower() == "true":
    from sqlalchemy.pool import NullPool
    pool_class = NullPool

engine = create_async_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=1800,  # Recycle connections every 30 minutes to prevent stale connections
    echo=settings.DEBUG,
    poolclass=pool_class,
)

# Async Session Factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy models.
    Uses SQLAlchemy 2.0 DeclarativeBase.
    """

    pass


async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for FastAPI endpoints to get an async database session.
    Ensures the session is closed after the request is finished.

    Also stores the session in request.state for middleware access.
    """
    async with AsyncSessionLocal() as session:
        # Store session on request.state for middleware access
        request.state.db_session = session
        try:
            yield session
        finally:
            await session.close()
