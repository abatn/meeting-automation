import asyncio
import os
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from backend.app.core.config import settings
from backend.app.core.database import Base
from backend.app.models.meeting import Meeting
from backend.app.models.recording import Recording
from fastapi import HTTPException
from backend.app.models.transcription import Transcription, TranscriptionStatus
from backend.app.models.user import User, UserRole
import backend.app.services.pv_service as pv_service
from backend.app.services import pv_service
from backend.app.services.mistral_client import MOCK_PV_RESPONSE
import json

# Override settings for testing
settings.DATABASE_URL = "sqlite+aiosqlite:///./test.db"
settings.MOCK_MISTRAL_API = True

# Setup test database
engine = create_async_engine(settings.DATABASE_URL, echo=True)
TestingSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession, expire_on_commit=False)

async def create_test_db_and_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def drop_test_db_and_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

async def test_pv_generation_with_mock_mistral():
    print("Starting PV generation test with mock Mistral...")
    await drop_test_db_and_tables()
    await create_test_db_and_tables()

    async with TestingSessionLocal() as db:
        try:
            # Create a mock user
            user = User(
                email="test@example.com",
                username="testuser",
                hashed_password="hashedpassword",
                full_name="Test User",
                role=UserRole.PARTICIPANT,
                is_active=True
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
            print(f"Created mock user: {user.email}")

            # Create a mock meeting
            meeting = Meeting(
                title="Test Meeting for PV Generation",
                description="A meeting to test PV generation.",
                date=datetime.now(),
                duration=60, # Beispiel: 60 Minuten
                organizer_id=user.id
            )
            db.add(meeting)
            await db.commit()
            await db.refresh(meeting)
            print(f"Created mock meeting: {meeting.title}")

            # Create a mock recording
            recording = Recording(
                meeting_id=meeting.id,
                file_path="mock/path/to/recording.mp3",
                file_size=1024,
                duration=60.0
            )
            db.add(recording)
            await db.commit()
            await db.refresh(recording)
            print(f"Created mock recording for meeting {meeting.id}")

            # Create a mock transcription
            transcription = Transcription(
                meeting_id=meeting.id,
                recording_id=recording.id,
                content="This is a test transcription content for generating a PV.",
                language="en",
                status=TranscriptionStatus.COMPLETED
            )
            db.add(transcription)
            await db.commit()
            await db.refresh(transcription)
            print(f"Created mock transcription for meeting {meeting.id}")

            # Mock current_user dependency for generate_pv
            async def mock_get_current_user():
                return user

            # Generate PV
            print("Calling generate_pv...")
            pv = await pv_service.generate_pv(
                meeting_id=meeting.id,
                transcription_id=transcription.id,
                db=db,
                current_user=await mock_get_current_user()
            )

            assert pv is not None
            assert pv.meeting_id == meeting.id
            assert pv.content == MOCK_PV_RESPONSE["choices"][0]["message"]["content"]
            print("PV generation successful with mock Mistral!")
            print(f"Generated PV ID: {pv.id}")
            print(f"Generated PV Content:\n{pv.content}")

        except Exception as e:
            print(f"Test failed: {e}")
            raise
        finally:
            await db.close()
            await drop_test_db_and_tables()
            print("Cleaned up test database.")

async def test_pv_validation_as_dg():
    print("\nStarting PV validation test as DG...")
    await drop_test_db_and_tables()
    await create_test_db_and_tables()

    async with TestingSessionLocal() as db:
        try:
            # Create a mock DG user
            dg_user = User(
                email="dg@example.com",
                username="dguser",
                hashed_password="hashedpassword",
                full_name="DG User",
                role=UserRole.DG,
                is_active=True
            )
            db.add(dg_user)
            await db.commit()
            await db.refresh(dg_user)
            print(f"Created mock DG user: {dg_user.email}")

            # Create a mock meeting
            meeting = Meeting(
                title="Test Meeting for PV Validation",
                description="A meeting to test PV validation.",
                date=datetime.now(),
                duration=60,
                organizer_id=dg_user.id
            )
            db.add(meeting)
            await db.commit()
            await db.refresh(meeting)
            print(f"Created mock meeting: {meeting.title}")

            # Create a mock recording
            recording = Recording(
                meeting_id=meeting.id,
                file_path="mock/path/to/recording.mp3",
                file_size=1024,
                duration=60.0
            )
            db.add(recording)
            await db.commit()
            await db.refresh(recording)
            print(f"Created mock recording for meeting {meeting.id}")

            # Create a mock transcription
            transcription = Transcription(
                meeting_id=meeting.id,
                recording_id=recording.id,
                content="This is a test transcription content for generating a PV.",
                language="en",
                status=TranscriptionStatus.COMPLETED
            )
            db.add(transcription)
            await db.commit()
            await db.refresh(transcription)
            print(f"Created mock transcription for meeting {meeting.id}")

            # Generate PV first
            pv = await pv_service.generate_pv(
                meeting_id=meeting.id,
                transcription_id=transcription.id,
                db=db,
                current_user=dg_user
            )
            print(f"Generated PV ID: {pv.id}")

            # Validate PV as DG
            validated_pv = await pv_service.validate_pv(
                pv_id=pv.id,
                user=dg_user,
                db=db,
                comment="Looks good!"
            )

            assert validated_pv is not None
            assert validated_pv.id == pv.id
            assert validated_pv.validated_at is not None
            assert validated_pv.validated_by_id == dg_user.id
            assert validated_pv.validation_comment == "Looks good!"
            print("PV validation as DG successful!")

        except Exception as e:
            print(f"Test failed: {e}")
            raise
        finally:
            await db.close()
            await drop_test_db_and_tables()
            print("Cleaned up test database.")

async def test_pv_validation_as_normal_user_403():
    print("\nStarting PV validation test as normal user (expecting 403)...")
    await drop_test_db_and_tables()
    await create_test_db_and_tables()

    async with TestingSessionLocal() as db:
        try:
            # Create a mock normal user
            normal_user = User(
                email="normal@example.com",
                username="normaluser",
                hashed_password="hashedpassword",
                full_name="Normal User",
                role=UserRole.PARTICIPANT,
                is_active=True
            )
            db.add(normal_user)
            await db.commit()
            await db.refresh(normal_user)
            print(f"Created mock normal user: {normal_user.email}")

            # Create a mock meeting
            meeting = Meeting(
                title="Test Meeting for PV Validation (Normal User)",
                description="A meeting to test PV validation by a normal user.",
                date=datetime.now(),
                duration=60,
                organizer_id=normal_user.id
            )
            db.add(meeting)
            await db.commit()
            await db.refresh(meeting)
            print(f"Created mock meeting: {meeting.title}")

            # Create a mock recording
            recording = Recording(
                meeting_id=meeting.id,
                file_path="mock/path/to/recording_normal_user.mp3",
                file_size=1024,
                duration=60.0
            )
            db.add(recording)
            await db.commit()
            await db.refresh(recording)
            print(f"Created mock recording for meeting {meeting.id} (normal user test)")

            # Create a mock transcription
            transcription = Transcription(
                meeting_id=meeting.id,
                recording_id=recording.id,
                content="This is a test transcription content for generating a PV.",
                language="en",
                status=TranscriptionStatus.COMPLETED
            )
            db.add(transcription)
            await db.commit()
            await db.refresh(transcription)
            print(f"Created mock transcription for meeting {meeting.id}")

            # Generate PV first
            pv = await pv_service.generate_pv(
                meeting_id=meeting.id,
                transcription_id=transcription.id,
                db=db,
                current_user=normal_user
            )
            print(f"Generated PV ID: {pv.id}")

            # Attempt to validate PV as normal user (should raise HTTPException 403)
            try:
                await pv_service.validate_pv(
                    pv_id=pv.id,
                    user=normal_user,
                    db=db,
                    comment="I approve!"
                )
                assert False, "Expected HTTPException 403, but no exception was raised."
            except HTTPException as e:
                assert e.status_code == 403
                assert "Only DGs can validate PVs" in e.detail
                print("PV validation as normal user correctly raised 403 Forbidden!")

        except Exception as e:
            print(f"Test failed: {e}")
            raise
        finally:
            await db.close()
            await drop_test_db_and_tables()
            print("Cleaned up test database.")

async def main():
    await test_pv_generation_with_mock_mistral()
    await test_pv_validation_as_dg()
    await test_pv_validation_as_normal_user_403()
    await test_extract_decisions_from_pv()

async def test_extract_decisions_from_pv():
    print("\nStarting decision extraction test...")
    await drop_test_db_and_tables()
    await create_test_db_and_tables()

    async with TestingSessionLocal() as db:
        try:
            # Create a mock user
            user = User(
                email="extractor@example.com",
                username="extractoruser",
                hashed_password="hashedpassword",
                full_name="Extractor User",
                role=UserRole.PARTICIPANT,
                is_active=True
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
            print(f"Created mock user: {user.email}")

            # Create a mock meeting
            meeting = Meeting(
                title="Test Meeting for Decision Extraction",
                description="A meeting to test decision extraction.",
                date=datetime.now(),
                duration=60,
                organizer_id=user.id
            )
            db.add(meeting)
            await db.commit()
            await db.refresh(meeting)
            print(f"Created mock meeting: {meeting.title}")

            # Create a mock recording
            recording = Recording(
                meeting_id=meeting.id,
                file_path="mock/path/to/recording.mp3",
                file_size=1024,
                duration=60.0
            )
            db.add(recording)
            await db.commit()
            await db.refresh(recording)
            print(f"Created mock recording for meeting {meeting.id}")

            # Create a mock transcription
            transcription = Transcription(
                meeting_id=meeting.id,
                recording_id=recording.id,
                content="The team decided to proceed with Project X. We also agreed to postpone the marketing campaign.",
                language="en",
                status=TranscriptionStatus.COMPLETED
            )
            db.add(transcription)
            await db.commit()
            await db.refresh(transcription)
            print(f"Created mock transcription for meeting {meeting.id}")

            # Generate PV first (with mock content that Mistral would process)
            pv_content_for_extraction = "During the meeting, it was decided that Project X will be prioritized. Another key decision was to delay the marketing campaign until next quarter."
            pv = await pv_service.generate_pv(
                meeting_id=meeting.id,
                transcription_id=transcription.id,
                db=db,
                current_user=user
            )
            pv.content = pv_content_for_extraction # Override with content suitable for decision extraction
            db.add(pv)
            await db.commit()
            await db.refresh(pv)
            print(f"Generated PV ID: {pv.id} with content: {pv.content}")

            # Mock MistralClient.extract_decisions to return a JSON string
            original_extract_decisions = pv_service.mistral_client.extract_decisions
            pv_service.mistral_client.extract_decisions = lambda content: asyncio.sleep(0.1, result=json.dumps(["Project X will be prioritized", "Marketing campaign delayed until next quarter"]))

            # Extract decisions
            print("Calling extract_decisions...")
            decisions_result = await pv_service.extract_decisions(pv.content)
            extracted_decisions = json.loads(decisions_result)

            assert extracted_decisions == ["Project X will be prioritized", "Marketing campaign delayed until next quarter"]
            print(f"Extracted decisions: {extracted_decisions}")

            # Update PV with extracted decisions
            pv_update_data = pv_service.PVUpdate(decisions=extracted_decisions)
            updated_pv = await pv_service.update_pv(pv.id, pv_update_data, db=db, current_user=user)

            assert updated_pv.decisions == extracted_decisions
            print("PV updated with extracted decisions successfully!")

        except Exception as e:
            print(f"Test failed: {e}")
            raise
        finally:
            pv_service.mistral_client.extract_decisions = original_extract_decisions # Restore original mock
            await db.close()
            await drop_test_db_and_tables()
            print("Cleaned up test database.")

if __name__ == "__main__":
    asyncio.run(main())
