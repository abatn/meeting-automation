import pytest
import pytest_asyncio
import asyncio
from typing import Generator, AsyncGenerator
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from starlette.requests import Request
from app.main import app
from app.core.database import Base, get_db
from app.core.config import settings
from app.core.security import get_password_hash, verify_password
from sqlalchemy.pool import NullPool
import os

# IMPORTANT: Import all model classes BEFORE engine creation to populate Base.metadata
# This ensures ALL tables are created via Base.metadata.create_all()
from app.models.user import User as UserModel, Role as RoleModel
from app.models.client import Client as ClientModel
from app.models.meeting import Meeting as MeetingModel, Participant as ParticipantModel, Agenda as AgendaModel
from app.models.action import Action as ActionModel, Assignment as AssignmentModel, ActionSuggestion as SuggestionModel, ActionStatus as DBActionStatus
from app.models.pv import PV as PVModel
from app.models.recording import Recording as RecordingModel
from app.models.transcription import Transcription as TranscriptionModel, Speaker as SpeakerModel
from app.models.audit_log import AuditLog as AuditLogModel
from app.models.setting import BrandingSettings as BrandingSettingsModel
from app.models.team import TeamMember as TeamModel
from app.models.meeting_room import MeetingRoom as MeetingRoomModel
from app.models.facture import Facture as FactureModel
from app.models.consent import ConsentLog, ConsentType
from app.models.usage_minute import UsageMinute as UsageMinuteModel

# Event loop policy (fixes pytest-asyncio DeprecationWarning)
# Using event_loop_policy instead of custom event_loop fixture (recommended for pytest-asyncio >= 0.23)
@pytest.fixture(scope="session")
def event_loop_policy():
    return asyncio.get_event_loop_policy()

# Entscheide, welche Datenbank für Tests verwendet wird:
# - Für E2E-Tests: Nutze die PostgreSQL-Datenbank aus settings.DATABASE_URL
# - Für Unit/Integration-Tests: Nutze schnelle SQLite-In-Memory-DB
E2E_MODE = (
    os.getenv("E2E_TEST", "").lower() == "true"
    or os.getenv("TEST_USE_PROD_DB", "").lower() == "true"
    or os.getenv("USE_POSTGRES_FOR_TESTS", "").lower() == "true"
)

if E2E_MODE:
    # E2E-Tests: Echte PostgreSQL-Datenbank verwenden
    TEST_DATABASE_URL = settings.DATABASE_URL
else:
    # Unit/Integration-Tests: Schnelle SQLite-In-Memory-DB
    TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"

# Use NullPool to avoid asyncpg enum OID caching issues in tests
engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
TestingSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

@pytest_asyncio.fixture(scope="function")
async def db_session() -> Generator:
    """
    Provides a database session for each test function.
    For Unit/Integration tests: creates fresh schema on start, drops on end.
    For E2E tests: uses existing schema (created by backend) and ensures test data exists.
    """
    # In non-E2E modes, create fresh schema; in E2E mode, use existing DB
    if not E2E_MODE:
        # Delete stale test.db to avoid schema mismatch
        import pathlib
        test_db = pathlib.Path("./test.db")
        if test_db.exists():
            test_db.unlink()
        # Dispose engine to clear pooled connections and cached enum OIDs
        await engine.dispose()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async with TestingSessionLocal() as session:
        # Insert required roles and test user if missing (idempotent)
        from app.models.user import Role as RoleModel
        default_roles = [
            {"id": "role-dg-universal", "name": "dg"},
            {"id": "role-admin-universal", "name": "admin"},
            {"id": "role-manager-universal", "name": "manager"},
            {"id": "role-participant-universal", "name": "participant"},
        ]
        for role_dict in default_roles:
            existing = await session.execute(
                select(RoleModel).where(RoleModel.name == role_dict["name"])
            )
            if not existing.scalar_one_or_none():
                role = RoleModel(**role_dict)
                session.add(role)
        await session.commit()

        from app.models.client import Client as ClientModel, SubscriptionStatus
        from app.models.user import User as UserModel, UserStatus

        test_client_result = await session.execute(
            select(ClientModel).where(ClientModel.id == "test-client-id")
        )
        test_client = test_client_result.scalar_one_or_none()
        if not test_client:
            test_client = ClientModel(
                id="test-client-id",
                company_name="Test Client",
                subscription_status=SubscriptionStatus.ACTIVE,
            )
            session.add(test_client)
            await session.flush()

        test_user_result = await session.execute(
            select(UserModel).where(UserModel.id == "test-user-id")
        )
        test_user = test_user_result.scalar_one_or_none()
        _test_pw = os.getenv("E2E_TEST_USER_PASSWORD", "TestPassword123!")
        _test_email = os.getenv("E2E_TEST_USER_EMAIL", "test@example.com")
        if not test_user:
            dg_role_result = await session.execute(
                select(RoleModel).where(RoleModel.name == "dg")
            )
            dg_role = dg_role_result.scalar_one_or_none()
            test_user = UserModel(
                id="test-user-id",
                client_id="test-client-id",
                email=_test_email,
                hashed_password=get_password_hash(_test_pw),
                status=UserStatus.ACTIVE.value,
                is_superuser=True,
                roles=[dg_role] if dg_role else []
            )
            session.add(test_user)
        else:
            updated = False
            if test_user.email != _test_email:
                test_user.email = _test_email
                updated = True
            if not verify_password(_test_pw, test_user.hashed_password):
                test_user.hashed_password = get_password_hash(_test_pw)
                updated = True

        dg_user_result = await session.execute(
            select(UserModel).where(UserModel.email == "dg@meeting.tn")
        )
        dg_user = dg_user_result.scalar_one_or_none()
        # NUR überschreiben wenn E2E_TEST=true UND Secret gesetzt
        # Sonst: Password123! aus seed_users.py respektieren
        _is_e2e_env = os.getenv("E2E_TEST", "").lower() == "true"
        _dg_pw = os.getenv("E2E_TEST_USER_PASSWORD", "Password123!") if _is_e2e_env else "Password123!"
        if not dg_user:
            dg_role_result = await session.execute(
                select(RoleModel).where(RoleModel.name == "dg")
            )
            dg_role = dg_role_result.scalar_one_or_none()
            dg_user = UserModel(
                id="dg-test-user-id",
                client_id="test-client-id",
                email="dg@meeting.tn",
                hashed_password=get_password_hash(_dg_pw),
                status=UserStatus.ACTIVE.value,
                is_superuser=True,
                roles=[dg_role] if dg_role else []
            )
            session.add(dg_user)
        elif _is_e2e_env and not verify_password(_dg_pw, dg_user.hashed_password):
            # NUR überschreiben wenn E2E_TEST=true (verhindert Hash-Überschreibung auf Staging/Prod)
            dg_user.hashed_password = get_password_hash(_dg_pw)

        # Seed ConsentLog for E2E seed users so recording/livekit gates pass
        if os.getenv("E2E_TEST", "").lower() == "true":
            import uuid
            from datetime import datetime, timezone
            for seed_user in [test_user, dg_user]:
                for ctype in (ConsentType.C1_AUDIO, ConsentType.C2_VOICE, ConsentType.C3_SHARING, ConsentType.C4_STORAGE):
                    existing = await session.execute(
                        select(ConsentLog).where(
                            ConsentLog.user_id == seed_user.id,
                            ConsentLog.consent_type == ctype,
                        )
                    )
                    if not existing.scalar_one_or_none():
                        session.add(ConsentLog(
                            id=str(uuid.uuid4()),
                            user_id=seed_user.id,
                            client_id="test-client-id",
                            consent_type=ctype,
                            consented=True,
                            consent_version="1.0",
                            created_at=datetime.now(timezone.utc),
                        ))

        await session.commit()

        yield session

    # Cleanup: only drop schema in non-E2E mode; in E2E mode DB is shared and managed by docker-compose
    if not E2E_MODE:
        await engine.dispose()
        # Delete test.db instead of drop_all to avoid FK ordering issues
        import pathlib
        test_db = pathlib.Path("./test.db")
        if test_db.exists():
            test_db.unlink()


@pytest_asyncio.fixture(scope="function")
async def db_session_with_audit(db_session: AsyncSession) -> Generator[AsyncSession, None, None]:
    """
    Independent DB session for audit logging verification.
    Uses the same schema created by db_session.
    Depends on db_session to ensure schema and test data exist.
    """
    async with TestingSessionLocal() as session:
        yield session


from app.api import deps
from app.models.user import User as UserModel, UserStatus
from unittest.mock import patch, MagicMock

@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db(request: Request):
        # Manually set request.state.db_session since we're bypassing real get_db
        request.state.db_session = db_session
        yield db_session
        # Note: db_session lifecycle managed by db_session fixture, not here

    # Override get_db with test session. The middleware will access it via request.state.db_session
    app.dependency_overrides[get_db] = override_get_db

    from jose import jwt
    import uuid
    from datetime import datetime, timedelta, timezone
    # Token payload matches the test user created in db_session
    # Unique jti per test prevents blacklist collisions (ISO 27001 A.5.17)
    token_payload = {
        "sub": "test-user-id",
        "client_id": "test-client-id",
        "jti": str(uuid.uuid4()),
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    token = jwt.encode(token_payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    headers = {"Authorization": f"Bearer {token}"}

    # Celery eager mode is enabled for tests, so no need to mock send_task.
    # Keep boto3 mock as a precaution for any S3 operations.
    with patch("boto3.client"):
        async with AsyncClient(app=app, base_url="http://test", headers=headers) as ac:
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
        "company_name": "Test Company"
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
