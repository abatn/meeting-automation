from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from typing import Optional, List
from backend.app.models.recording import Recording, RecordingStatus
from backend.app.schemas.recording import RecordingCreate, RecordingUpdate
from backend.app.models.user import User, UserRole
from backend.app.utils.storage import storage_service
from fastapi import UploadFile, HTTPException, status
import uuid
import mimetypes
import logging
import os
from pydub import AudioSegment
from pydub.utils import mediainfo

logger = logging.getLogger(__name__)

MAX_FILE_SIZE_MB = 500
ALLOWED_AUDIO_TYPES = ["audio/mpeg", "audio/wav", "audio/x-wav", "audio/aac", "audio/ogg", "audio/flac"]

async def get_recording_by_id(db: AsyncSession, recording_id: int) -> Optional[Recording]:
    """Holt eine Aufnahme anhand der ID."""
    result = await db.execute(
        select(Recording)
        .where(Recording.id == recording_id)
        .options(selectinload(Recording.meeting)) # Load meeting relationship
    )
    return result.scalar_one_or_none()

async def get_recordings_by_meeting(db: AsyncSession, meeting_id: int) -> List[Recording]:
    """Holt alle Aufnahmen für ein bestimmtes Meeting, mit eager loading für zugehörige Beziehungen."""
    result = await db.execute(
        select(Recording)
        .where(Recording.meeting_id == meeting_id)
        .options(
            selectinload(Recording.meeting),
            selectinload(Recording.transcription)
        )
        .order_by(Recording.uploaded_at.desc())
    )
    return result.scalars().all()

async def create_recording(
    db: AsyncSession,
    recording_data: RecordingCreate
) -> Recording:
    """Erstellt einen neuen Aufnahme-Eintrag in der Datenbank."""
    # All necessary fields are in recording_data now
    recording_dict = recording_data.dict()
    recording_dict.pop("transcription_id", None) # Remove transcription_id as it's a relationship, not a direct column
    db_recording = Recording(
        **recording_dict
    )
    db.add(db_recording)
    await db.commit()
    await db.refresh(db_recording)
    return db_recording

async def upload_recording(
    db: AsyncSession,
    meeting_id: int,
    uploader_id: int,
    file: UploadFile
) -> Recording:
    """
    Verarbeitet den Upload einer Audio-Datei, speichert sie in S3/MinIO
    und erstellt einen Datenbankeintrag.
    """
    # 1. Validate file
    await validate_audio_file(file)

    # 2. Create a unique filename and S3 object name
    file_extension = mimetypes.guess_extension(file.content_type)
    if not file_extension:
        file_extension = ".bin" # Fallback for unknown types
    object_name = f"recordings/{meeting_id}/{uuid.uuid4()}{file_extension}"

    # 3. Create initial DB entry with UPLOADING status
    initial_recording_data = RecordingCreate(
        meeting_id=meeting_id,
        uploader_id=uploader_id,
        file_path=object_name,
        file_size=file.size,
        status=RecordingStatus.UPLOADING,
        duration=0.0 # Temporary duration, will be updated after extraction
    )
    db_recording = await create_recording(
        db=db,
        recording_data=initial_recording_data
    )

    # 4. Upload to S3/MinIO
    try:
        file.file.seek(0) # Ensure file pointer is at the beginning
        upload_success = await storage_service.upload_to_s3(
            file.file, object_name, file.content_type
        )
        if not upload_success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to upload file to storage."
            )
        
        # 5. Extract metadata and update DB entry
        file.file.seek(0) # Reset file pointer again for metadata extraction
        duration = await extract_audio_metadata(file.file)
        
        db_recording.duration = duration
        db_recording.status = RecordingStatus.COMPLETED # Or PROCESSING if further steps are needed
        await db.commit()
        await db.refresh(db_recording)
        
        return db_recording

    except HTTPException:
        # If upload fails, delete the initial DB entry
        await db.delete(db_recording)
        await db.commit()
        raise
    except Exception as e:
        logger.error(f"Error during recording upload process: {e}")
        await db.delete(db_recording)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during upload: {e}"
        )

async def update_recording_status(
    db: AsyncSession,
    recording_id: int,
    new_status: RecordingStatus,
    user_id: int # For permission check
) -> Optional[Recording]:
    """Aktualisiert den Status einer Aufnahme."""
    recording = await get_recording_by_id(db, recording_id)
    if not recording:
        return None
    
    # Permission check: Only uploader or admin can change status
    if recording.uploader_id != user_id:
        user_result = await db.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()
        if not user or user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update recording status."
            )

    try:
        recording.status = new_status
        await db.commit()
        await db.refresh(recording)
        return recording
    except Exception as e:
        await db.rollback()
        raise e

async def delete_recording(db: AsyncSession, recording_id: int, user_id: int) -> bool:
    """Löscht eine Aufnahme aus der Datenbank und aus S3/MinIO."""
    recording = await get_recording_by_id(db, recording_id)
    if not recording:
        return False
    
    # Prüfe Berechtigung
    if recording.uploader_id != user_id:
        user_result = await db.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()
        if not user or user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to delete this recording."
            )
    
    # Delete from S3/MinIO
    delete_success = await storage_service.delete_from_s3(recording.file_path)
    if not delete_success:
        logger.error(f"Failed to delete file {recording.file_path} from S3.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete recording file from storage."
        )

    try:
        await db.delete(recording)
        await db.commit()
        return True
    except Exception as e:
        await db.rollback()
        raise e

async def get_recording_download_url(db: AsyncSession, recording_id: int, user_id: int) -> Optional[str]:
    """Generiert eine signierte Download-URL für eine Aufnahme."""
    recording = await get_recording_by_id(db, recording_id)
    if not recording:
        return None
    
    # Permission check: Only uploader, meeting participant or admin can download
    # This requires fetching meeting participants, which is not directly available here.
    # For now, let's assume only uploader or admin can download.
    # TODO: Implement proper meeting participant check
    if recording.uploader_id != user_id:
        user_result = await db.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()
        if not user or user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to download this recording."
            )

    if recording.status != RecordingStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Recording is not yet completed or available for download."
        )

    url = await storage_service.get_s3_download_url(recording.file_path)
    return url

async def validate_audio_file(file: UploadFile):
    """Validiert die hochgeladene Audio-Datei (Format und Größe)."""
    if file.content_type not in ALLOWED_AUDIO_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported audio file type: {file.content_type}. Allowed types are: {', '.join(ALLOWED_AUDIO_TYPES)}"
        )
    
    # FastAPI's UploadFile.size is only available after the file has been read
    # For validation before reading the entire file into memory, we might need
    # to read chunks or rely on client-side validation.
    # For now, we'll assume file.size is populated after initial upload.
    if file.size and file.size > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds the maximum limit of {MAX_FILE_SIZE_MB}MB."
        )

async def extract_audio_metadata(file_object) -> Optional[float]:
    """Extrahiert Metadaten wie Dauer aus der Audio-Datei."""
    try:
        # pydub needs a file path or a file-like object that can be read
        # For in-memory file, we might need to save it temporarily or use BytesIO
        # For simplicity, assuming file_object is a path or a BytesIO object
        # that pydub can handle.
        # If file_object is a SpooledTemporaryFile from UploadFile, it can be passed directly.
        
        # Save to a temporary file to use with pydub/ffmpeg
        temp_file_path = f"/tmp/{uuid.uuid4()}.tmp"
        with open(temp_file_path, "wb") as temp_file:
            temp_file.write(file_object.read())
        
        audio_info = mediainfo(temp_file_path)
        duration = float(audio_info.get("duration", 0))
        
        os.remove(temp_file_path) # Clean up temp file
        return duration
    except Exception as e:
        logger.warning(f"Could not extract audio metadata: {e}")
        return None