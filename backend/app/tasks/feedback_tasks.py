"""
Celery tasks for feedback processing (learn_from_feedback endpoint).
Runs heavy operations (S3 download, ONNX, Mistral) in background.
"""
import asyncio
import concurrent.futures
import logging
from app.tasks.celery_app import celery_app
from app.core.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Run async coroutine from sync context."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    
    if loop is None:
        asyncio.run(coro)
    else:
        import concurrent.futures
        
        async def _wrapper():
            return await coro
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            def _run_in_thread():
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    return new_loop.run_until_complete(_wrapper())
                finally:
                    new_loop.close()
            
            future = pool.submit(_run_in_thread)
            return future.result(timeout=60)


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
    _run_async(
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
