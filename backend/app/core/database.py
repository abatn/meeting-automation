from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from .config import settings

DATABASE_URL = settings.DATABASE_URL
SYNC_DATABASE_URL = settings.DATABASE_URL.replace("postgresql+asyncpg", "postgresql") # For synchronous engine

# Asynchronous engine and session
engine = create_async_engine(DATABASE_URL, echo=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession)

# Synchronous engine and session for middleware/background tasks
sync_engine = create_engine(SYNC_DATABASE_URL, echo=True)
SyncSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)

Base = declarative_base()

async def get_db():
    async with SessionLocal() as session:
        yield session

@contextmanager
def get_db_session_sync():
    """
    Provides a synchronous session for use in middleware or other synchronous contexts.
    """
    session = SyncSessionLocal()
    try:
        yield session
    finally:
        session.close()
