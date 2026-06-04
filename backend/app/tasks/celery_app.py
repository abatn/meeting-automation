import os
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
    broker_connection_retry_on_startup=True,
)

# Enable eager mode for E2E tests to run tasks synchronously in the same process
if os.getenv("E2E_TEST", "").lower() == "true":
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True

# Auto-discover tasks in the 'app.tasks' package
celery_app.autodiscover_tasks(
    [
        "app.tasks.email_tasks",
        "app.tasks.transcription_tasks",
        "app.tasks.data_retention",
        "app.tasks.feedback_tasks",
    ]
)

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
