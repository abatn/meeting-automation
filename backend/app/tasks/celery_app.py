import os
from celery import Celery
from celery.schedules import crontab
from kombu import Queue
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
    # Production reliability settings
    task_acks_late=True,                    # Ack AFTER completion, not receipt
    worker_prefetch_multiplier=1,           # Don't prefetch long tasks
    task_time_limit=600,                    # 10min hard kill
    task_soft_time_limit=540,               # 9min soft warning
    result_expires=3600,                    # Clean up results after 1h
    # Queue isolation
    task_routes={
        'process_recording': {'queue': 'transcription'},
        'process_feedback_resolution': {'queue': 'transcription'},
        'send_reminder_via_n8n': {'queue': 'email'},
        'daily_reminder_task': {'queue': 'email'},
        'send_invitation_email': {'queue': 'email'},
        'cleanup_old_data_task': {'queue': 'maintenance'},
    },
    task_queues=(
        Queue('transcription', routing_key='transcription'),
        Queue('transcription_gratuit', routing_key='transcription_gratuit'),
        Queue('transcription_pro', routing_key='transcription_pro'),
        Queue('email', routing_key='email'),
        Queue('maintenance', routing_key='maintenance'),
    ),
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
        "app.tasks.storage_tasks",
    ]
)


async def get_transcription_queue(client_id: str, db=None) -> str:
    """Return the Celery queue for transcription tasks based on client plan.
    
    GRATUIT → transcription_gratuit (1Gi workers, no LLM overhead)
    PRO/ENTREPRISE → transcription_pro (3Gi workers, Sentinel LLM available)
    """
    try:
        from app.models.client import Client
        from sqlalchemy import select
        
        if db is None:
            return "transcription_gratuit"
        
        result = await db.execute(select(Client.subscription_plan).where(Client.id == client_id))
        plan = result.scalar()
        
        if plan and plan.value in ("pro", "entrepise"):
            return "transcription_pro"
        return "transcription_gratuit"
    except Exception:
        return "transcription_gratuit"


def get_transcription_queue(client_id: str) -> str:
    """Return the Celery queue for transcription tasks based on client plan.
    
    GRATUIT → transcription_gratuit (1Gi workers, no LLM overhead)
    PRO/ENTREPRISE → transcription_pro (3Gi workers, Sentinel LLM available)
    """
    try:
        from app.models.client import Client
        from sqlalchemy import select
        from app.core.database import AsyncSessionLocal
        import asyncio
        
        async def _get_plan():
            async with AsyncSessionLocal() as session:
                result = await session.execute(select(Client.subscription_plan).where(Client.id == client_id))
                plan = result.scalar()
                return plan
        
        plan = asyncio.run(_get_plan())
        
        if plan and plan.value in ("pro", "entrepise"):
            return "transcription_pro"
        return "transcription_gratuit"
    except Exception:
        # Fallback: if we can't determine the plan, use the default queue
        return "transcription"

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
    "check-storage-quotas": {
        "task": "check_storage_quotas",
        "schedule": crontab(minute="*/15"),  # Every 15 minutes (ISO 27001 A.8.26)
    },
}
