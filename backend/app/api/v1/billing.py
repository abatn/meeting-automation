from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.models.user import User as UserModel
from app.schemas.billing import (
    Facture, 
    UsageMinute, 
    CheckoutSessionCreate, 
    CheckoutSessionResponse
)
from app.services.billing_service import BillingService

router = APIRouter()

@router.post("/checkout", response_model=CheckoutSessionResponse)
async def create_checkout_session(
    *,
    db: AsyncSession = Depends(deps.get_db),
    session_in: CheckoutSessionCreate,
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """
    Create a checkout session for a specific subscription plan.
    """
    if session_in.plan not in ["PRO", "ENTREPRISE"]:
        raise HTTPException(status_code=400, detail="Invalid plan selected")
        
    service = BillingService(db)
    result = await service.create_checkout_session(
        client_id=current_user.client_id,
        plan_name=session_in.plan,
        success_url=session_in.success_url,
        cancel_url=session_in.cancel_url
    )
    return result


@router.get("/invoices", response_model=List[Facture])
async def list_my_invoices(
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """
    Retrieve all invoices for the current tenant.
    """
    service = BillingService(db)
    return await service.get_client_invoices(current_user.client_id)


@router.get("/usage", response_model=dict)
async def get_my_usage(
    period: Optional[str] = None,
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """
    Retrieve transcription usage summary for the current tenant.
    """
    service = BillingService(db)
    return await service.get_usage_summary(current_user.client_id, period)


# --- Admin Only Endpoints (Alternative to admin router) ---

@router.get("/admin/client/{client_id}/invoices", response_model=List[Facture])
async def admin_list_client_invoices(
    client_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """
    Allow system admin to view invoices for any client.
    """
    if not current_user.is_superuser and current_user.role != "system_admin":
        raise HTTPException(status_code=403, detail="Not enough privileges")
        
    service = BillingService(db)
    return await service.get_client_invoices(client_id)
