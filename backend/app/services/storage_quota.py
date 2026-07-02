import logging
import boto3
from app.core.config import settings, get_bucket_name
from app.models.client import SubscriptionPlan

logger = logging.getLogger(__name__)

STORAGE_QUOTAS = {
    SubscriptionPlan.GRATUIT: 1 * 1024 * 1024 * 1024,       # 1 GB
    SubscriptionPlan.PRO: 10 * 1024 * 1024 * 1024,           # 10 GB
    SubscriptionPlan.ENTREPRISE: 50 * 1024 * 1024 * 1024,    # 50 GB
}


def get_storage_usage_bytes(client_id: str) -> int:
    """Summiert alle S3-Objekte für einen Tenant (eigener Bucket)."""
    s3 = boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
    )
    bucket = get_bucket_name(client_id)
    total = 0
    try:
        paginator = s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket):
            for obj in page.get("Contents", []):
                total += obj["Size"]
    except Exception as e:
        logger.warning(f"Could not check storage for {client_id}: {e}")
    return total


def get_storage_quota(subscription_plan: SubscriptionPlan) -> int:
    """Gibt das Speicherlimit in Bytes für einen Plan zurück."""
    return STORAGE_QUOTAS.get(subscription_plan, STORAGE_QUOTAS[SubscriptionPlan.GRATUIT])


def check_storage_quota(client_id: str, subscription_plan: SubscriptionPlan, additional_bytes: int = 0) -> dict:
    """Prüft ob ein Upload das Speicherlimit überschreitet.
    
    Returns:
        {"allowed": True/False, "used": bytes, "quota": bytes, "free": bytes}
    """
    used = get_storage_usage_bytes(client_id)
    quota = get_storage_quota(subscription_plan)
    free = max(0, quota - used)
    allowed = (used + additional_bytes) <= quota
    
    if not allowed:
        logger.warning(
            f"Storage quota exceeded for {client_id}: "
            f"used={used}, additional={additional_bytes}, quota={quota}"
        )
    
    return {
        "allowed": allowed,
        "used": used,
        "quota": quota,
        "free": free,
    }
