"""
Storage Quota Monitoring Tasks (ISO 27001 A.8.26 Multi-Tenant)
Periodic checks for storage usage thresholds (50%, 70%, 90%)
"""
import logging
import asyncio
from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


@shared_task(name="check_storage_quotas")
def check_storage_quotas():
    """
    Prüft alle Tenants auf Storage-Quota-Überschreitung.
    Wird alle 15 Minuten von Celery Beat ausgeführt.
    """
    from app.core.database import AsyncSessionLocal
    from app.services.storage_quota import get_storage_usage_bytes, get_storage_quota
    from app.models.client import Client as ClientModel
    from sqlalchemy import select
    
    async def _check_all():
        async with AsyncSessionLocal() as db:
            from app.main import STORAGE_USAGE
            
            result = await db.execute(select(ClientModel))
            clients = result.scalars().all()
            
            alerts_created = 0
            for client in clients:
                client_id = str(client.id)
                usage_bytes = get_storage_usage_bytes(client_id)
                quota_bytes = get_storage_quota(client.subscription_plan)
                usage_percent = round((usage_bytes / quota_bytes * 100), 2) if quota_bytes > 0 else 0
                
                # Update Prometheus Gauge (ISO 27001 A.8.26)
                STORAGE_USAGE.labels(client_id=client_id).set(usage_bytes)
                
                # Check thresholds and log alerts
                if usage_percent >= 90:
                    logger.warning(
                        f"STORAGE CRITICAL: Client {client.company_name} ({client_id}) "
                        f"at {usage_percent}% ({usage_bytes}/{quota_bytes} bytes)"
                    )
                    alerts_created += 1
                elif usage_percent >= 70:
                    logger.warning(
                        f"STORAGE WARNING HIGH: Client {client.company_name} ({client_id}) "
                        f"at {usage_percent}% ({usage_bytes}/{quota_bytes} bytes)"
                    )
                    alerts_created += 1
                elif usage_percent >= 50:
                    logger.info(
                        f"STORAGE WARNING: Client {client.company_name} ({client_id}) "
                        f"at {usage_percent}% ({usage_bytes}/{quota_bytes} bytes)"
                    )
                    alerts_created += 1
            
            logger.info(
                f"Storage quota check completed: {len(clients)} tenants, "
                f"{alerts_created} alerts"
            )
    
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(_check_all())
        else:
            loop.run_until_complete(_check_all())
    except Exception as e:
        logger.error(f"Storage quota check failed: {e}")
