"""
Celery tasks for feedback processing (learn_from_feedback endpoint).
Runs heavy operations (S3 download, ONNX, Mistral) in background.
"""
import asyncio
import logging
from app.tasks.celery_app import celery_app
from app.core.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


@celery_app.task(
    name="process_feedback_resolution",
    bind=True,
    autoretry_for=(Exception,),
    max_retries=3,
    retry_backoff=True,
    retry_backoff_max=60,
)
def process_feedback_resolution(
    self,
    suggestion_id: str,
    client_id: str,
    action: str,
    user_id: str,
) -> dict:
    """
    Background task to process feedback resolution.
    Runs heavy operations (S3 download, ONNX inference, Mistral API) asynchronously.
    """
    asyncio.run(
        _process_feedback_async(suggestion_id, client_id, action, user_id)
    )

    return {
        "suggestion_id": suggestion_id,
        "status": "resolved",
        "action": action,
    }


async def _process_feedback_async(
    suggestion_id: str,
    client_id: str,
    action: str,
    user_id: str,
) -> None:
    """Async helper to process feedback in Celery task."""
    async with AsyncSessionLocal() as db:
        from app.services.action_service import ActionService
        try:
            action_service = ActionService(db)
            await action_service.learn_from_feedback(
                suggestion_id,
                client_id,
                action,
                user_id=user_id,
            )
            logger.info(f"Feedback resolved: suggestion={suggestion_id}, action={action}")
        except Exception as e:
            logger.error(f"Feedback resolution failed: {e}", exc_info=True)
            await db.rollback()
            raise
        finally:
            await db.close()
