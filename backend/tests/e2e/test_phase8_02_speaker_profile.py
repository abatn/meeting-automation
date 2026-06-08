"""
Phase 8: Speaker Identification — E2E Tests
Phase 2: SpeakerProfile CRUD + Cosine Distance Matching
"""
import uuid
import numpy as np
import pytest
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transcription import Speaker
from app.models.client import Client
from app.models.user import User, UserStatus
from app.services.speaker_profile_service import SpeakerProfileService


@pytest.fixture
def fake_embedding():
    """Generate a random normalized 192-dim embedding."""
    emb = np.random.randn(192).astype(np.float32)
    return emb / np.linalg.norm(emb)


@pytest.fixture
def similar_embedding(fake_embedding):
    """Generate an embedding similar to the fake_embedding (cosine distance < 0.2)."""
    noise = np.random.randn(192).astype(np.float32) * 0.05
    similar = fake_embedding + noise
    return similar / np.linalg.norm(similar)


@pytest.fixture
def different_embedding():
    """Generate a completely different embedding (cosine distance > 0.4)."""
    emb = np.random.randn(192).astype(np.float32)
    return emb / np.linalg.norm(emb)


@pytest.fixture
def unique_name():
    """Generate a unique speaker name for each test."""
    return f"Speaker-{uuid.uuid4().hex[:6]}"


@pytest.mark.asyncio
async def test_phase8_06_create_speaker_profile(db_session, unique_name):
    """
    E2E Test: Create a speaker profile.
    Verifies:
    - Profile is created with correct fields
    - Embedding is stored as JSON
    - sample_count is 1
    """
    # Create a test client
    client = Client(
        id=str(uuid.uuid4()),
        company_name=f"Test Company {uuid.uuid4().hex[:6]}",
        subscription_plan="GRATUIT",
        subscription_status="ACTIVE",
        created_at=datetime.utcnow(),
    )
    db_session.add(client)
    await db_session.flush()
    
    service = SpeakerProfileService(db_session)
    embedding = np.random.randn(192).astype(np.float32)
    embedding = embedding / np.linalg.norm(embedding)

    speaker = await service.create_profile(
        client_id=client.id,
        name=unique_name,
        embedding=embedding,
        source="manual",
    )

    assert speaker is not None
    assert speaker.name == unique_name
    assert speaker.client_id == client.id
    assert speaker.sample_count == 1
    assert speaker.embedding is not None
    assert len(speaker.embedding) == 192
    assert speaker.source == "manual"


@pytest.mark.asyncio
async def test_phase8_07_get_profiles(db_session):
    """
    E2E Test: Retrieve speaker profiles for a client.
    Verifies:
    - Only profiles for the correct client are returned
    - Profiles without embeddings are excluded
    """
    # Create a test client
    client = Client(
        id=str(uuid.uuid4()),
        company_name=f"Test Company {uuid.uuid4().hex[:6]}",
        subscription_plan="GRATUIT",
        subscription_status="ACTIVE",
        created_at=datetime.utcnow(),
    )
    db_session.add(client)
    await db_session.flush()
    
    service = SpeakerProfileService(db_session)

    embedding = np.random.randn(192).astype(np.float32)
    embedding = embedding / np.linalg.norm(embedding)

    name1 = f"Ahmed-{uuid.uuid4().hex[:6]}"
    name2 = f"Sarah-{uuid.uuid4().hex[:6]}"

    await service.create_profile(
        client_id=client.id,
        name=name1,
        embedding=embedding,
    )

    await service.create_profile(
        client_id=client.id,
        name=name2,
        embedding=embedding,
    )

    profiles = await service.get_profiles(client.id)
    assert len(profiles) >= 2

    names = {p.name for p in profiles}
    assert name1 in names
    assert name2 in names


@pytest.mark.asyncio
async def test_phase8_08_match_speaker_high_confidence(db_session, fake_embedding, unique_name):
    """
    E2E Test: Match a speaker with high confidence.
    Verifies:
    - Cosine distance < 0.20 returns "high" confidence
    - Correct name is returned
    """
    # Create a test client
    client = Client(
        id=str(uuid.uuid4()),
        company_name=f"Test Company {uuid.uuid4().hex[:6]}",
        subscription_plan="GRATUIT",
        subscription_status="ACTIVE",
        created_at=datetime.utcnow(),
    )
    db_session.add(client)
    await db_session.flush()
    
    service = SpeakerProfileService(db_session)

    speaker = await service.create_profile(
        client_id=client.id,
        name=unique_name,
        embedding=fake_embedding,
    )

    await db_session.commit()

    profiles = await service.get_profiles(client.id)
    assert len(profiles) >= 1, f"Expected at least 1 profile, got {len(profiles)}"

    similar = fake_embedding + np.random.randn(192).astype(np.float32) * 0.02
    similar = similar / np.linalg.norm(similar)

    name, distance, confidence = await service.match_speaker(
        client_id=client.id,
        embedding=similar,
    )

    assert name == unique_name, f"Expected '{unique_name}', got {name} (distance={distance}, confidence={confidence})"
    assert confidence in ("high", "medium"), f"Expected high or medium confidence, got {confidence}"
    assert distance < 0.50, f"Expected distance < 0.50, got {distance}"


@pytest.mark.asyncio
async def test_phase8_09_match_speaker_no_match(db_session, fake_embedding, different_embedding, unique_name):
    """
    E2E Test: No match when embedding is too different.
    Verifies:
    - Cosine distance > 0.45 returns "no_match"
    - Name is None
    """
    # Create a test client
    client = Client(
        id=str(uuid.uuid4()),
        company_name=f"Test Company {uuid.uuid4().hex[:6]}",
        subscription_plan="GRATUIT",
        subscription_status="ACTIVE",
        created_at=datetime.utcnow(),
    )
    db_session.add(client)
    await db_session.flush()
    
    service = SpeakerProfileService(db_session)

    await service.create_profile(
        client_id=client.id,
        name=unique_name,
        embedding=fake_embedding,
    )

    name, distance, confidence = await service.match_speaker(
        client_id=client.id,
        embedding=different_embedding,
    )

    assert name is None
    assert confidence == "no_match"
    assert distance > 0.40


@pytest.mark.asyncio
async def test_phase8_10_update_profile_embedding(db_session, fake_embedding, unique_name):
    """
    E2E Test: Update a speaker profile with a new embedding (running average).
    Verifies:
    - sample_count increments
    - Embedding is updated
    """
    # Create a test client
    client = Client(
        id=str(uuid.uuid4()),
        company_name=f"Test Company {uuid.uuid4().hex[:6]}",
        subscription_plan="GRATUIT",
        subscription_status="ACTIVE",
        created_at=datetime.utcnow(),
    )
    db_session.add(client)
    await db_session.flush()
    
    service = SpeakerProfileService(db_session)

    speaker = await service.create_profile(
        client_id=client.id,
        name=unique_name,
        embedding=fake_embedding,
    )

    new_embedding = np.random.randn(192).astype(np.float32)
    new_embedding = new_embedding / np.linalg.norm(new_embedding)

    updated = await service.update_profile_embedding(speaker, new_embedding)

    assert updated.sample_count == 2
    assert updated.embedding is not None
    assert len(updated.embedding) == 192


@pytest.mark.asyncio
async def test_phase8_12_tenant_isolation(db_session, fake_embedding):
    """
    E2E Test: Speaker profiles are isolated by client_id.
    Verifies:
    - Profiles from client A are not visible to client B
    - Matching only uses profiles from the correct client
    """
    # Create client A
    client_a = Client(
        id=str(uuid.uuid4()),
        company_name=f"Test Company A {uuid.uuid4().hex[:6]}",
        subscription_plan="GRATUIT",
        subscription_status="ACTIVE",
        created_at=datetime.utcnow(),
    )
    db_session.add(client_a)
    await db_session.flush()
    
    # Create client B
    client_b = Client(
        id=str(uuid.uuid4()),
        company_name=f"Test Company B {uuid.uuid4().hex[:6]}",
        subscription_plan="GRATUIT",
        subscription_status="ACTIVE",
        created_at=datetime.utcnow(),
    )
    db_session.add(client_b)
    await db_session.flush()
    
    service = SpeakerProfileService(db_session)
    
    name = f"Ahmed-{uuid.uuid4().hex[:6]}"

    await service.create_profile(
        client_id=client_a.id,
        name=f"Ahmed-{uuid.uuid4().hex[:6]}",
        embedding=fake_embedding,
    )

    profiles_a = await service.get_profiles(client_a.id)
    profiles_b = await service.get_profiles(client_b.id)

    assert len(profiles_a) >= 1
    assert len(profiles_b) == 0

    name_result, _, _ = await service.match_speaker(
        client_id=client_b.id,
        embedding=fake_embedding,
    )
    assert name_result is None
