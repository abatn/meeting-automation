from typing import Any, List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel

from app.api import deps
from app.models.user import User as UserModel, UserRole
from app.models.client import Client as ClientModel, SubscriptionStatus, SubscriptionPlan
from app.models.usage_minute import UsageMinute
from app.models.cms import PricingPlan
from app.schemas.client import Client, ClientUpdate
from app.services.audit_service import AuditService

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

@router.get("/clients", response_model=List[dict])
async def list_all_clients(
    status: Optional[SubscriptionStatus] = None,
    plan: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(deps.get_db),
    admin: UserModel = Depends(get_system_admin),
) -> Any:
    """
    Retrieve all clients with usage stats (System Admin only).
    """
    stmt = select(ClientModel)
    
    if status:
        stmt = stmt.where(ClientModel.subscription_status == status)
    if plan:
        stmt = stmt.where(ClientModel.subscription_plan == plan)
        
    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    clients = result.scalars().all()
    
    # Enrich with current month usage
    period = datetime.now().strftime("%Y-%m")
    enriched_clients = []
    
    for c in clients:
        usage_stmt = select(func.sum(UsageMinute.minutes)).where(
            UsageMinute.client_id == c.id,
            UsageMinute.period == period
        )
        usage_res = await db.execute(usage_stmt)
        monthly_mins = usage_res.scalar() or 0
        
        c_dict = {
            "id": c.id,
            "company_name": c.company_name,
            "subscription_plan": c.subscription_plan,
            "subscription_status": c.subscription_status,
            "minutes_included": c.minutes_included,
            "minutes_used_total": c.minutes_used or 0,
            "minutes_used_month": monthly_mins,
            "created_at": c.created_at
        }
        enriched_clients.append(c_dict)
        
    return enriched_clients


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
        
    old_status = client.subscription_status
    client.subscription_status = status_update.status
    db.add(client)
    await db.commit()
    await db.refresh(client)
    
    # Log to Audit Trail
    await AuditService.log_action(
        db=db,
        client_id=client_id,
        user_id=admin.id,
        action="UPDATE_CLIENT_STATUS",
        table_name="clients",
        record_id=client_id,
        old_values={"status": old_status},
        new_values={"status": status_update.status}
    )
    
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
    
    # 2. Client counts by plan (only ACTIVE clients)
    plan_stmt = (
        select(ClientModel.subscription_plan, func.count(ClientModel.id))
        .where(ClientModel.subscription_status == SubscriptionStatus.ACTIVE)
        .group_by(ClientModel.subscription_plan)
    )
    plan_result = await db.execute(plan_stmt)
    plan_counts = {str(p.name if hasattr(p, 'name') else p): count for p, count in plan_result.all()}
    
    # 3. Get prices from CMS pricing_plans (fallback to defaults)
    prices = {}
    for plan_code in ["PRO", "ENTREPRISE"]:
        price_stmt = select(PricingPlan.price_monthly).where(PricingPlan.plan_code == plan_code, PricingPlan.is_active == True)
        price_result = await db.execute(price_stmt)
        price_row = price_result.scalar_one_or_none()
        prices[plan_code] = price_row if price_row else (99 if plan_code == "PRO" else 499)
    
    # 4. Calculate Estimated Monthly Revenue (only ACTIVE clients)
    revenue = 0
    active_pro = plan_counts.get("PRO", 0)
    active_enterprise = plan_counts.get("ENTREPRISE", 0)
    
    revenue += active_pro * prices["PRO"]
    revenue += active_enterprise * prices["ENTREPRISE"]
    
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
    import time
    from app.services.monitoring_service import MonitoringService
    
    # Run independent checks concurrently
    import asyncio
    container_metrics, db_metrics, redis_metrics, minio_metrics, rmq_metrics, ai_metrics, n8n_metrics = await asyncio.gather(
        MonitoringService.get_container_metrics(),
        MonitoringService.get_database_metrics(db),
        MonitoringService.get_redis_metrics(),
        MonitoringService.get_minio_metrics(),
        MonitoringService.get_rabbitmq_metrics(),
        MonitoringService.get_ai_metrics(),
        MonitoringService.get_n8n_metrics()
    )

    return {
        "timestamp": time.time(),
        "containers": container_metrics,
        "services": {
            "database": db_metrics,
            "redis": redis_metrics,
            "rabbitmq": rmq_metrics,
            "storage": minio_metrics,
            "n8n": n8n_metrics,
            "ai_services": ai_metrics
        }
    }
