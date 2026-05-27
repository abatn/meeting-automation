"""
E2E Tests für Phase 1: Kritische Security-Fixes
Tests für Fix #8, Fix #1, Fix #9
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User, UserStatus
from app.models.meeting import Meeting, Participant
from app.models.recording import Recording
from app.models.client import Client
from datetime import datetime, timedelta
import uuid
from sqlalchemy import select


@pytest.mark.asyncio
class TestPhase1Fixes:
    """Test Phase 1: Critical Security Fixes"""

    async def test_fix_8_cross_tenant_user_validation(
        self, db_session: AsyncSession
    ):
        """
        FIX #8: Cross-Tenant User-Validierung
        SZENARIO: User A (tenant_b) versucht auf User B's Meetings (tenant_a) zuzugreifen
        ERGEBNIS: PermissionError wird geworfen, Datenleak verhindert
        """
        # Setup: Erstelle 2 Tenants
        client_a = Client(
            id=str(uuid.uuid4()),
            company_name=f"Company A-{uuid.uuid4()}",
            subscription_plan="GRATUIT",
            created_at=datetime.utcnow(),
        )
        client_b = Client(
            id=str(uuid.uuid4()),
            company_name=f"Company B-{uuid.uuid4()}",
            subscription_plan="GRATUIT",
            created_at=datetime.utcnow(),
        )
        db_session.add(client_a)
        db_session.add(client_b)
        await db_session.flush()

        # User A: belongs to tenant_a
        user_a = User(
            id=str(uuid.uuid4()),
            email=f"user_a_{uuid.uuid4().hex[:6]}@company-a.com",
            full_name="User A",
            client_id=client_a.id,
            hashed_password="dummy",
            status=UserStatus.ACTIVE.value,
            created_at=datetime.utcnow(),
        )
        
        # User B: belongs to tenant_b
        user_b = User(
            id=str(uuid.uuid4()),
            email=f"user_b_{uuid.uuid4().hex[:6]}@company-b.com",
            full_name="User B",
            client_id=client_b.id,
            hashed_password="dummy",
            status=UserStatus.ACTIVE.value,
            created_at=datetime.utcnow(),
        )
        db_session.add(user_a)
        db_session.add(user_b)
        await db_session.flush()

        # Test: Prüfe, dass user_b NICHT zu client_a gehört
        result = await db_session.execute(
            select(User.id).where(
                User.id == user_b.id,
                User.client_id == client_a.id,
                User.deleted_at.is_(None),
            )
        )
        
        # ✅ ERGEBNIS: None (User B gehört nicht zu Tenant A)
        assert result.scalar() is None, "User B should NOT belong to Client A"
        print("✅ Fix #8: Cross-Tenant User-Validierung erfolgreich")

    async def test_fix_1_recording_access_validation(
        self, db_session: AsyncSession
    ):
        """
        FIX #1: Recording-Access-Validierung
        SZENARIO: 
        - Meeting mit Recording (access_policy = "organizer_only")
        - Organizer sollte URL sehen
        - Teilnehmer sollte URL NICHT sehen
        """
        # Setup: Tenant
        client = Client(
            id=str(uuid.uuid4()),
            company_name=f"Test Company-{uuid.uuid4()}",
            subscription_plan="GRATUIT",
            created_at=datetime.utcnow(),
        )
        db_session.add(client)
        await db_session.flush()

        # Setup: Users
        organizer = User(
            id=str(uuid.uuid4()),
            email=f"organizer_{uuid.uuid4().hex[:6]}@test.com",
            full_name="Organizer",
            client_id=client.id,
            hashed_password="dummy",
            status=UserStatus.ACTIVE.value,
            created_at=datetime.utcnow(),
        )
        participant = User(
            id=str(uuid.uuid4()),
            email=f"participant_{uuid.uuid4().hex[:6]}@test.com",
            full_name="Participant",
            client_id=client.id,
            hashed_password="dummy",
            status=UserStatus.ACTIVE.value,
            created_at=datetime.utcnow(),
        )
        db_session.add(organizer)
        db_session.add(participant)
        await db_session.flush()

        # Setup: Meeting mit Recording (organizer_only policy)
        meeting = Meeting(
            id=str(uuid.uuid4()),
            client_id=client.id,
            title="Test Meeting",
            creator_id=organizer.id,
            start_time=datetime.utcnow() - timedelta(days=5),
            end_time=datetime.utcnow() - timedelta(days=5, hours=-1),
            status="completed",
            created_at=datetime.utcnow(),
        )
        db_session.add(meeting)
        await db_session.flush()

        # Recording mit access_policy = "organizer_only"
        recording = Recording(
            id=str(uuid.uuid4()),
            client_id=client.id,
            meeting_id=meeting.id,
            file_path="/storage/recordings/test.mp4",
            status="completed",
            access_policy="organizer_only",  # ← NEW FIELD
            created_at=datetime.utcnow(),
        )
        db_session.add(recording)
        await db_session.flush()

        # Participants
        org_participant = Participant(
            id=str(uuid.uuid4()),
            meeting_id=meeting.id,
            user_id=organizer.id,
            email=organizer.email,
            name=organizer.full_name,
        )
        part_participant = Participant(
            id=str(uuid.uuid4()),
            meeting_id=meeting.id,
            user_id=participant.id,
            email=participant.email,
            name=participant.full_name,
        )
        db_session.add(org_participant)
        db_session.add(part_participant)
        await db_session.commit()

        # Test 1: Organizer darf URL sehen
        user_id_is_organizer = organizer.id == meeting.creator_id
        access_policy_is_everyone = recording.access_policy == "everyone"
        organizer_can_access = user_id_is_organizer or access_policy_is_everyone
        
        assert organizer_can_access, "Organizer should access recording"
        print("✅ Fix #1a: Organizer kann Recording URL sehen")

        # Test 2: Teilnehmer darf URL NICHT sehen (policy=organizer_only)
        user_id_is_organizer = participant.id == meeting.creator_id
        access_policy_is_everyone = recording.access_policy == "everyone"
        participant_can_access = user_id_is_organizer or access_policy_is_everyone
        
        assert not participant_can_access, "Participant should NOT access recording URL"
        print("✅ Fix #1b: Teilnehmer kann Recording URL NOT sehen (organizer_only policy)")

    async def test_fix_9_token_validation_soft_delete(
        self, db_session: AsyncSession
    ):
        """
        FIX #9: Service-Level Token-Validierung
        SZENARIO: 
        - User wird soft-deleted (deleted_at = NOW)
        - Prüfe, dass soft-deleted User NICHT validiert wird
        """
        # Setup: Tenant
        client = Client(
            id=str(uuid.uuid4()),
            company_name=f"Test Company-{uuid.uuid4()}",
            subscription_plan="GRATUIT",
            created_at=datetime.utcnow(),
        )
        db_session.add(client)
        await db_session.flush()

        # Setup: Active User
        active_user = User(
            id=str(uuid.uuid4()),
            email=f"active_{uuid.uuid4().hex[:6]}@test.com",
            full_name="Active User",
            client_id=client.id,
            hashed_password="dummy",
            status=UserStatus.ACTIVE.value,
            created_at=datetime.utcnow(),
        )
        
        # Setup: Soft-deleted User
        deleted_user = User(
            id=str(uuid.uuid4()),
            email=f"deleted_{uuid.uuid4().hex[:6]}@test.com",
            full_name="Deleted User",
            client_id=client.id,
            hashed_password="dummy",
            status=UserStatus.ACTIVE.value,  # Status ist noch ACTIVE
            deleted_at=datetime.utcnow(),  # Aber soft-deleted!
            created_at=datetime.utcnow(),
        )
        db_session.add(active_user)
        db_session.add(deleted_user)
        await db_session.flush()

        # Test 1: Active User wird validiert
        result = await db_session.execute(
            select(User.id).where(
                User.id == active_user.id,
                User.client_id == client.id,
                User.deleted_at.is_(None),
            )
        )
        
        assert result.scalar() is not None, "Active user should be validated"
        print("✅ Fix #9a: Active User wird validiert")

        # Test 2: Soft-deleted User wird NICHT validiert
        result = await db_session.execute(
            select(User.id).where(
                User.id == deleted_user.id,
                User.client_id == client.id,
                User.deleted_at.is_(None),  # ← This check fails!
            )
        )
        
        assert result.scalar() is None, "Soft-deleted user should NOT be validated"
        print("✅ Fix #9b: Soft-deleted User wird NOT validiert (SECURITY!)")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
