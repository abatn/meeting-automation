from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from typing import Optional, List
from app.models.recording import Recording
from app.schemas.recording import RecordingCreate, RecordingUpdate
from app.models.user import User, UserRole

async def get_recording_by_id(db: AsyncSession, recording_id: int) -> Optional[Recording]:
    """Holt eine Aufnahme anhand der ID."""
    result = await db.execute(
        select(Recording)
        .where(Recording.id == recording_id)
        .options(selectinload(Recording.uploader))
    )
    return result.scalar_one_or_none()

async def get_recordings(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 100,
    meeting_id: Optional[int] = None,
    uploader_id: Optional[int] = None
) -> List[Recording]:
    """Holt eine Liste von Aufnahmen mit optionalen Filtern."""
    query = select(Recording).options(selectinload(Recording.uploader))
    
    filters = []
    if meeting_id:
        filters.append(Recording.meeting_id == meeting_id)
    if uploader_id:
        filters.append(Recording.uploader_id == uploader_id)
    
    if filters:
        query = query.where(and_(*filters))
    
    query = query.order_by(Recording.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

async def create_recording(
    db: AsyncSession,
    recording_data: RecordingCreate,
    uploader_id: int
) -> Recording:
    """Erstellt eine neue Aufnahme."""
    db_recording = Recording(
        **recording_data.dict(),
        uploader_id=uploader_id
    )
    db.add(db_recording)
    await db.commit()
    await db.refresh(db_recording)
    return db_recording

async def update_recording(
    db: AsyncSession,
    recording_id: int,
    recording_data: RecordingUpdate,
    user_id: int
) -> Optional[Recording]:
    """Aktualisiert eine Aufnahme (nur Uploader oder Admin)."""
    recording = await get_recording_by_id(db, recording_id)
    if not recording:
        return None
    
    # Prüfe Berechtigung
    if recording.uploader_id != user_id:
        user_result = await db.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()
        if not user or user.role != UserRole.ADMIN:
            return None
    
    update_data = recording_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(recording, field, value)
    
    await db.commit()
    await db.refresh(recording)
    return recording

async def delete_recording(db: AsyncSession, recording_id: int, user_id: int) -> bool:
    """Löscht eine Aufnahme (nur Uploader oder Admin)."""
    recording = await get_recording_by_id(db, recording_id)
    if not recording:
        return False
    
    # Prüfe Berechtigung
    if recording.uploader_id != user_id:
        user_result = await db.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()
        if not user or user.role != UserRole.ADMIN:
            return False
    
    await db.delete(recording)
    await db.commit()
    return True