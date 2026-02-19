import logging
from datetime import datetime, timedelta

from backend.app.tasks.celery_app import celery_app
from backend.app.core.config import settings
from backend.app.core.database import SessionLocal
from backend.app.models.recording import Recording, RecordingStatus
from backend.app.models.meeting import Meeting, MeetingStatus
from backend.app.models.transcription import Transcription
from backend.app.models.pv import PV
from backend.app.models.audit_log import AuditLog
from backend.app.models.action import Action, ActionStatus
from backend.app.services.notification_service import notification_service
from backend.app.services.action_service import action_service
from backend.app.services.audit_service import audit_service
from backend.app.utils.storage import storage_service
from sqlalchemy.future import select
from sqlalchemy import delete, and_

logger = logging.getLogger(__name__)

@celery_app.task(bind=True, default_retry_delay=settings.CELERY_TASK_DEFAULT_RETRY_DELAY, max_retries=settings.CELERY_TASK_MAX_RETRIES)
async def cleanup_old_recordings(self):
    logger.info("Starting cleanup_old_recordings task.")
    async with SessionLocal() as db:
        try:
            retention_period = datetime.utcnow() - timedelta(days=settings.RECORDING_RETENTION_DAYS)
            
            # Select recordings older than retention_period that are not associated with an active meeting
            # Or if the meeting itself is archived/completed and no longer needs the recording
            recordings_to_delete = (await db.execute(
                select(Recording).where(
                    and_(
                        Recording.uploaded_at < retention_period,
                        Recording.status != RecordingStatus.PROCESSING # Don't delete if still processing
                    )
                )
            )).scalars().all()

            for recording in recordings_to_delete:
                # Check if associated meeting is still active or requires the recording
                # This is a simplified check; a more robust solution might involve checking meeting status
                # or explicit flags. For now, we assume if it's old and not processing, it can be deleted.
                meeting = await db.get(Meeting, recording.meeting_id)
                if meeting and meeting.status in [MeetingStatus.PLANNED, MeetingStatus.IN_PROGRESS]:
                    logger.info(f"Skipping recording {recording.id} as its meeting {meeting.id} is still active.")
                    continue

                # Delete file from storage
                if recording.file_path:
                    await storage_service.delete_from_s3(recording.file_path)
                    logger.info(f"Deleted recording file: {recording.file_path}")

                # Create audit log entry
                await audit_service.create_audit_log(
                    db,
                    user_id=None, # System action
                    event_type="RECORDING_DELETION",
                    resource_type="Recording",
                    resource_id=recording.id,
                    details=f"Recording {recording.id} (Meeting {recording.meeting_id}) automatically deleted due to retention policy."
                )
                
                # Delete recording entry from DB
                await db.delete(recording)
                logger.info(f"Deleted recording {recording.id} from database.")
            
            await db.commit()
            logger.info("Finished cleanup_old_recordings task successfully.")
        except Exception as exc:
            await db.rollback()
            logger.error(f"Error in cleanup_old_recordings task: {exc}")
            raise self.retry(exc=exc)

@celery_app.task(bind=True, default_retry_delay=settings.CELERY_TASK_DEFAULT_RETRY_DELAY, max_retries=settings.CELERY_TASK_MAX_RETRIES)
async def archive_old_meetings(self):
    logger.info("Starting archive_old_meetings task.")
    async with SessionLocal() as db:
        try:
            archive_period = datetime.utcnow() - timedelta(days=settings.MEETING_ARCHIVE_DAYS)
            
            meetings_to_archive = (await db.execute(
                select(Meeting).where(
                    and_(
                        Meeting.end_time < archive_period,
                        Meeting.status != MeetingStatus.ARCHIVED
                    )
                )
            )).scalars().all()

            for meeting in meetings_to_archive:
                # Archive associated transcriptions and PVs
                transcriptions = (await db.execute(select(Transcription).where(Transcription.meeting_id == meeting.id))).scalars().all()
                for t in transcriptions:
                    t.status = TranscriptionStatus.ARCHIVED
                    db.add(t)
                
                pvs = (await db.execute(select(PV).where(PV.meeting_id == meeting.id))).scalars().all()
                for p in pvs:
                    p.status = PVStatus.ARCHIVED
                    db.add(p)

                meeting.status = MeetingStatus.ARCHIVED
                db.add(meeting)

                await audit_service.create_audit_log(
                    db,
                    user_id=None, # System action
                    event_type="MEETING_ARCHIVE",
                    resource_type="Meeting",
                    resource_id=meeting.id,
                    details=f"Meeting {meeting.id} automatically archived due to retention policy."
                )
                logger.info(f"Archived meeting {meeting.id} and its associated data.")
            
            await db.commit()
            logger.info("Finished archive_old_meetings task successfully.")
        except Exception as exc:
            await db.rollback()
            logger.error(f"Error in archive_old_meetings task: {exc}")
            raise self.retry(exc=exc)

@celery_app.task(bind=True, default_retry_delay=settings.CELERY_TASK_DEFAULT_RETRY_DELAY, max_retries=settings.CELERY_TASK_MAX_RETRIES)
async def delete_expired_audit_logs(self):
    logger.info("Starting delete_expired_audit_logs task.")
    async with SessionLocal() as db:
        try:
            retention_period = datetime.utcnow() - timedelta(days=settings.AUDIT_LOG_RETENTION_DAYS) # ISO 27001 typically 2 years
            
            # Optional: Export audit logs before deletion
            # For now, we just delete.
            
            await db.execute(
                delete(AuditLog).where(AuditLog.timestamp < retention_period)
            )
            await db.commit()
            logger.info(f"Deleted audit logs older than {retention_period.strftime('%Y-%m-%d %H:%M:%S')}.")
            logger.info("Finished delete_expired_audit_logs task successfully.")
        except Exception as exc:
            await db.rollback()
            logger.error(f"Error in delete_expired_audit_logs task: {exc}")
            raise self.retry(exc=exc)

@celery_app.task(bind=True, default_retry_delay=settings.CELERY_TASK_DEFAULT_RETRY_DELAY, max_retries=settings.CELERY_TASK_MAX_RETRIES)
async def check_overdue_actions(self):
    logger.info("Starting check_overdue_actions task.")
    async with SessionLocal() as db:
        try:
            overdue_actions = await action_service.check_overdue_actions(db)
            for action in overdue_actions:
                if action.status == ActionStatus.OPEN:
                    action.status = ActionStatus.OVERDUE
                    db.add(action)
                    await notification_service.send_action_overdue_notification(action) # Assuming this notification exists
                    logger.info(f"Action {action.id} marked as OVERDUE and notification sent.")
            await db.commit()
            logger.info("Finished check_overdue_actions task successfully.")
        except Exception as exc:
            await db.rollback()
            logger.error(f"Error in check_overdue_actions task: {exc}")
            raise self.retry(exc=exc)