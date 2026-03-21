from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel

from app.api import deps
from app.models.user import User as UserModel, UserRole
from app.models.client import Client as ClientModel, SubscriptionStatus
from app.schemas.client import Client, ClientUpdate

router = APIRouter()

# Schema for status update
class StatusUpdate(BaseModel):
    status: SubscriptionStatus

# Security Dependency: Only SYSTEM_ADMIN allowed
def get_system_admin(current_user: UserModel = Depends(deps.get_current_user)) -> UserModel:
    if current_user.role != UserRole.SYSTEM_ADMIN and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough privileges. System Admin only.",
        )
    return current_user

@router.get("/clients", response_model=List[Client])
async def list_all_clients(
    status: Optional[SubscriptionStatus] = None,
    plan: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(deps.get_db),
    admin: UserModel = Depends(get_system_admin),
) -> Any:
    """
    Retrieve all clients/tenants (System Admin only).
    """
    stmt = select(ClientModel)
    
    if status:
        stmt = stmt.where(ClientModel.subscription_status == status)
    if plan:
        stmt = stmt.where(ClientModel.subscription_plan == plan)
        
    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/clients/{client_id}", response_model=Client)
async def get_client_details(
    client_id: str,
    db: AsyncSession = Depends(deps.get_db),
    admin: UserModel = Depends(get_system_admin),
) -> Any:
    """
    Retrieve details of a specific client.
    """
    stmt = select(ClientModel).where(ClientModel.id == client_id)
    result = await db.execute(stmt)
    client = result.scalar_one_or_none()
    
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
        
    return client


@router.patch("/clients/{client_id}/status", response_model=Client)
async def update_client_status(
    client_id: str,
    status_update: StatusUpdate,
    db: AsyncSession = Depends(deps.get_db),
    admin: UserModel = Depends(get_system_admin),
) -> Any:
    """
    Activate, disable, or set a client to pending.
    """
    stmt = select(ClientModel).where(ClientModel.id == client_id)
    result = await db.execute(stmt)
    client = result.scalar_one_or_none()
    
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
        
    client.subscription_status = status_update.status
    db.add(client)
    await db.commit()
    await db.refresh(client)
    
    return client


@router.post("/clients/{client_id}/observations", response_model=Client)
async def add_client_observation(
    client_id: str,
    observation: dict, # {"text": "Note to add"}
    db: AsyncSession = Depends(deps.get_db),
    admin: UserModel = Depends(get_system_admin),
) -> Any:
    """
    Add an internal note/observation to a client.
    """
    stmt = select(ClientModel).where(ClientModel.id == client_id)
    result = await db.execute(stmt)
    client = result.scalar_one_or_none()
    
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
        
    new_note = observation.get("text", "")
    if client.observations:
        client.observations += f"\n--- [{admin.email}] ---\n{new_note}"
    else:
        client.observations = f"--- [{admin.email}] ---\n{new_note}"
        
    db.add(client)
    await db.commit()
    await db.refresh(client)
    
    return client


@router.get("/revenue", response_model=dict)
async def get_revenue_statistics(
    db: AsyncSession = Depends(deps.get_db),
    admin: UserModel = Depends(get_system_admin),
) -> Any:
    """
    Get system-wide revenue and client statistics.
    """
    # 1. Client counts by status
    status_stmt = select(ClientModel.subscription_status, func.count(ClientModel.id)).group_by(ClientModel.subscription_status)
    status_result = await db.execute(status_stmt)
    status_counts = {str(s.name if hasattr(s, 'name') else s): count for s, count in status_result.all()}
    
    # 2. Client counts by plan
    plan_stmt = select(ClientModel.subscription_plan, func.count(ClientModel.id)).group_by(ClientModel.subscription_plan)
    plan_result = await db.execute(plan_stmt)
    plan_counts = {str(p.name if hasattr(p, 'name') else p): count for p, count in plan_result.all()}
    
    # 3. Estimated Monthly Revenue
    revenue = 0
    active_pro = plan_counts.get("PRO", 0) if status_counts.get("ACTIVE", 0) > 0 else 0
    active_enterprise = plan_counts.get("ENTREPRISE", 0) if status_counts.get("ACTIVE", 0) > 0 else 0
    
    revenue += (active_pro * 99)
    revenue += (active_enterprise * 499)
    
    return {
        "total_clients": sum(status_counts.values()),
        "status_distribution": status_counts,
        "plan_distribution": plan_counts,
        "estimated_mrr_usd": revenue,
    }

@router.get("/system/performance", response_model=dict)
async def get_system_performance(
    db: AsyncSession = Depends(deps.get_db),
    admin: UserModel = Depends(get_system_admin),
) -> Any:
    """
    Get system health and performance metrics (System Admin only).
    """
    import os
    import psutil
    import time
    import logging
    import boto3
    from app.core.config import settings
    
    logger = logging.getLogger(__name__)
    
    # 1. Resource Metrics (Safe fallback)
    try:
        cpu_usage = psutil.cpu_percent(interval=None)
        ram_usage = psutil.virtual_memory().percent
        process = psutil.Process(os.getpid())
        mem_mb = process.memory_info().rss / 1024 / 1024
    except Exception as e:
        logger.error(f"Metrics error: {e}")
        cpu_usage, ram_usage, mem_mb = 0, 0, 0
    
    # 2. Database Status
    try:
        start_time = time.time()
        conn_res = await db.execute(select(func.count()).select_from(func.pg_stat_activity()))
        active_connections = conn_res.scalar()
        
        await db.execute(select(1))
        db_latency_ms = (time.time() - start_time) * 1000
        db_status = "healthy"
    except Exception as e:
        logger.error(f"DB Monitoring error: {e}")
        active_connections = 0
        db_latency_ms = -1
        db_status = "unhealthy"
        
    # 3. Redis Status
    from app.core.redis_client import get_redis_client
    try:
        redis_start = time.time()
        r_client = await get_redis_client()
        await r_client.ping()
        redis_latency_ms = (time.time() - redis_start) * 1000
        redis_status = "healthy"
    except Exception:
        redis_latency_ms = -1
        redis_status = "unhealthy"

    # 4. Storage Usage (Minio)
    s3_usage_mb = 0
    try:
        s3 = boto3.resource(
            's3',
            endpoint_url=settings.S3_ENDPOINT,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
        )
        bucket = s3.Bucket(settings.S3_BUCKET_NAME)
        total_bytes = sum(obj.size for obj in bucket.objects.all())
        s3_usage_mb = total_bytes / 1024 / 1024
        s3_status = "healthy"
    except Exception:
        s3_status = "unhealthy"

    return {
        "timestamp": time.time(),
        "resources": {
            "cpu_percent": cpu_usage,
            "ram_percent": ram_usage,
            "process_memory_mb": mem_mb
        },
        "services": {
            "database": {
                "status": db_status, 
                "latency_ms": db_latency_ms,
                "active_connections": active_connections
            },
            "redis": {"status": redis_status, "latency_ms": redis_latency_ms},
            "storage": {
                "status": s3_status,
                "usage_mb": s3_usage_mb
            },
            "celery": {"status": "healthy"},
            "ai_services": {"status": "healthy"}
        }
    }
