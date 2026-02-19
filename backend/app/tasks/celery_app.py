import os
from celery import Celery
from celery.schedules import crontab
import logging

from backend.app.core.config import settings

# Configure logging for Celery
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

def create_celery_app() -> Celery:
    celery_app = Celery(
        "meeting_automation_tasks",
        broker=settings.CELERY_BROKER_URL,
        backend=settings.CELERY_RESULT_BACKEND,
        include=[
            "backend.app.tasks.email_tasks",
            "backend.app.tasks.transcription_tasks",
            "backend.app.tasks.data_retention",
        ]
    )

    celery_app.conf.update(
        task_track_started=True,
        task_serializer='json',
        result_serializer='json',
        accept_content=['json'],
        timezone='Europe/Berlin',
        enable_utc=True,
        broker_connection_retry_on_startup=True,
        # Error-Handling und Retry-Logik für Tasks
        task_acks_late=True, # Acknowledge task only after it's done
        task_reject_on_worker_shutdown=True, # Requeue task if worker shuts down
        task_default_retry_delay=300, # 5 minutes
        task_max_retries=3, # Max 3 retries
    )

    # Celery Beat für periodische Tasks einrichten
    celery_app.conf.beat_schedule = {
        'cleanup-old-recordings-daily': {
            'task': 'backend.app.tasks.data_retention.cleanup_old_recordings',
            'schedule': crontab(hour=3, minute=0), # Täglich um 03:00 Uhr
            'args': (),
        },
        'archive-old-meetings-monthly': {
            'task': 'backend.app.tasks.data_retention.archive_old_meetings',
            'schedule': crontab(day_of_month=1, hour=4, minute=0), # Am ersten Tag des Monats um 04:00 Uhr
            'args': (),
        },
        'delete-expired-audit-logs-quarterly': {
            'task': 'backend.app.tasks.data_retention.delete_expired_audit_logs',
            'schedule': crontab(month_of_year='1,4,7,10', day_of_month=1, hour=5, minute=0), # Quartalsweise am ersten Tag des Monats um 05:00 Uhr
            'args': (),
        },
        'check-overdue-actions-daily': {
            'task': 'backend.app.tasks.data_retention.check_overdue_actions',
            'schedule': crontab(hour=2, minute=0), # Täglich um 02:00 Uhr
            'args': (),
        },
        'send-daily-digest-email-daily': {
            'task': 'backend.app.tasks.email_tasks.send_daily_digest',
            'schedule': crontab(hour=8, minute=0), # Täglich um 08:00 Uhr
            'args': (), # This task will need to iterate through users
        },
    }

    # Health-Check für Celery (optional, kann über Flower oder eigene Route implementiert werden)
    @celery_app.task
    def celery_health_check():
        logger.info("Celery health check task executed.")
        return "Celery is healthy!"

    return celery_app

celery_app = create_celery_app()