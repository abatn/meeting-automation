from celery import Celery
from celery.schedules import crontab
from app.core.config import settings

celery_app = Celery(
    "meeting_automation",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Africa/Tunis",
    enable_utc=True,
    task_track_started=True,
)

# Auto-discover tasks in the 'app.tasks' package
celery_app.autodiscover_tasks([
    "app.tasks.email_tasks",
    "app.tasks.transcription_tasks",
    "app.tasks.data_retention"
])

# Beat Schedule for periodic tasks
celery_app.conf.beat_schedule = {
    "send-daily-reminders": {
        "task": "daily_reminder_task",
        "schedule": crontab(hour=8, minute=0),  # Every day at 8:00 AM
    },
    "cleanup-expired-data": {
        "task": "app.tasks.data_retention.cleanup_old_data_task",
        "schedule": crontab(hour=2, minute=0),  # Every day at 2:00 AM
    },
}
