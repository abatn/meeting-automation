"""Consent management API (Phase 163 — INPDP Art.47 / Art.5 + GDPR).

Endpoints:
  POST /consent/grant   — record consent decisions (used at registration & in settings)
  GET  /consent/status  — current user's consent state
  POST /consent/withdraw — withdraw a previously granted consent
"""
import uuid
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api import deps
from app.models.user import User as UserModel
from app.models.consent import ConsentLog, ConsentType as ConsentTypeModel
from app.schemas.consent import (
    ConsentRequest,
    ConsentWithdrawRequest,
    ConsentStatusResponse,
    ConsentRecord,
)
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)

router = APIRouter()


async def grant_consents(
    db: AsyncSession,
    user_id: str,
    client_id: str,
    consents: list,
    consent_version: str,
    ip_address: str | None,
    user_agent: str | None,
) -> None:
    """Insert consent log rows. Idempotent per (user, type): updates if exists."""
    for grant in consents:
        ctype = ConsentTypeModel(grant.consent_type.value)
        existing = (
            await db.execute(
                select(ConsentLog).where(
                    ConsentLog.user_id == user_id,
                    ConsentLog.consent_type == ctype,
                )
            )
        ).scalar_one_or_none()

        if existing:
            existing.consented = grant.consented
            existing.consent_version = consent_version
            existing.withdrawn_at = None if grant.consented else existing.created_at
            existing.ip_address = ip_address
            existing.user_agent = user_agent
        else:
            db.add(
                ConsentLog(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    client_id=client_id,
                    consent_type=ctype,
                    consented=grant.consented,
                    consent_version=consent_version,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    withdrawn_at=None,
                )
            )

        await AuditService.log_action(
            db=db,
            client_id=client_id,
            action="CONSENT_GRANTED" if grant.consented else "CONSENT_DENIED",
            user_id=user_id,
            table_name="consent_logs",
            record_id=user_id,
            new_values={"consent_type": ctype.value, "consented": grant.consented},
            ip_address=ip_address or "internal",
            user_agent=user_agent or "api",
        )


@router.post("/grant", status_code=status.HTTP_200_OK)
async def grant(
    payload: ConsentRequest,
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_user),
) -> dict:
    """Record the user's consent decisions."""
    if not payload.consents:
        raise HTTPException(
            status_code=400, detail="No consent entries provided."
        )

    await grant_consents(
        db,
        user_id=current_user.id,
        client_id=current_user.client_id,
        consents=payload.consents,
        consent_version=payload.consent_version,
        ip_address=payload.ip_address,
        user_agent=payload.user_agent,
    )
    await db.commit()
    return {"status": "ok", "granted": [c.consent_type.value for c in payload.consents]}


@router.get("/status", response_model=ConsentStatusResponse)
async def status_endpoint(
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_user),
) -> ConsentStatusResponse:
    """Return the current user's consent state."""
    result = (
        await db.execute(
            select(ConsentLog).where(ConsentLog.user_id == current_user.id)
        )
    )
    rows = result.scalars().all()

    records = [ConsentRecord.model_validate(r) for r in rows]

    required_values = {
        ConsentTypeModel.C1_AUDIO.value,
        ConsentTypeModel.C3_SHARING.value,
        ConsentTypeModel.C4_STORAGE.value,
    }
    granted_values = {
        (r.consent_type.value if hasattr(r.consent_type, "value") else r.consent_type)
        for r in rows
        if r.consented
    }
    all_required = required_values.issubset(granted_values)

    return ConsentStatusResponse(consents=records, all_required_granted=all_required)


@router.post("/withdraw", status_code=status.HTTP_200_OK)
async def withdraw(
    payload: ConsentWithdrawRequest,
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_user),
) -> dict:
    """Withdraw a previously granted consent (never DELETE — set withdrawn_at)."""
    ctype = ConsentTypeModel(payload.consent_type.value)
    row = (
        await db.execute(
            select(ConsentLog).where(
                ConsentLog.user_id == current_user.id,
                ConsentLog.consent_type == ctype,
            )
        )
    ).scalar_one_or_none()

    if not row:
        raise HTTPException(status_code=404, detail="Consent record not found.")

    row.consented = False
    row.withdrawn_at = datetime.now(timezone.utc)

    await AuditService.log_action(
        db=db,
        client_id=current_user.client_id,
        action="CONSENT_WITHDRAWN",
        user_id=current_user.id,
        table_name="consent_logs",
        record_id=current_user.id,
        new_values={"consent_type": ctype.value},
        ip_address="internal",
        user_agent="api",
    )
    await db.commit()
    return {"status": "withdrawn", "consent_type": ctype.value}
