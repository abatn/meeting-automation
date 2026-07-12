import uuid
from typing import List, Any
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Request, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.models.consent import ConsentLog, ConsentType
from app.schemas.consent import ConsentGrant, ConsentResponse, ConsentStatusResponse
from app.services.audit_service import AuditService

router = APIRouter()


@router.get("/status", response_model=ConsentStatusResponse)
async def get_consent_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    result = await db.execute(
        select(ConsentLog).where(
            ConsentLog.user_id == current_user.id,
            ConsentLog.client_id == current_user.client_id,
            ConsentLog.withdrawn_at.is_(None),
        )
    )
    records = {r.consent_type: r.consented for r in result.scalars().all()}
    return ConsentStatusResponse(
        audio_recording=records.get("audio_recording", False),
        voice_profiling=records.get("voice_profiling", False),
        third_party_sharing=records.get("third_party_sharing", False),
        transcript_storage=records.get("transcript_storage", False),
    )


@router.post("/grant", response_model=List[ConsentResponse])
async def grant_consent(
    consents: List[ConsentGrant],
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    results = []
    ip = request.client.host if request.client else "unknown"
    ua = request.headers.get("user-agent", "unknown")

    for consent in consents:
        existing = await db.execute(
            select(ConsentLog).where(
                ConsentLog.user_id == current_user.id,
                ConsentLog.client_id == current_user.client_id,
                ConsentLog.consent_type == consent.consent_type,
            )
        )
        existing_record = existing.scalar_one_or_none()

        if existing_record:
            existing_record.consented = consent.consented
            existing_record.consent_version = consent.consent_version
            existing_record.ip_address = ip
            existing_record.user_agent = ua
            existing_record.timestamp = datetime.now(timezone.utc)
            existing_record.withdrawn_at = None if consent.consented else datetime.now(timezone.utc)
            record = existing_record
        else:
            record = ConsentLog(
                id=str(uuid.uuid4()),
                user_id=current_user.id,
                client_id=current_user.client_id,
                consent_type=consent.consent_type,
                consented=consent.consented,
                consent_version=consent.consent_version,
                ip_address=ip,
                user_agent=ua,
                withdrawn_at=None if consent.consented else datetime.now(timezone.utc),
            )
            db.add(record)

        results.append(record)
        await AuditService.log_action(
            db, client_id=current_user.client_id,
            action="CONSENT_GRANTED" if consent.consented else "CONSENT_WITHDRAWN",
            user_id=current_user.id,
            table_name="consent_logs",
            record_id=record.id,
            new_values={"consent_type": consent.consent_type, "consented": consent.consented},
            ip_address=ip,
            user_agent=ua,
        )

    await db.commit()
    for r in results:
        await db.refresh(r)
    return results


@router.post("/withdraw", response_model=ConsentResponse)
async def withdraw_consent(
    consent_type: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    valid_types = [ct.value for ct in ConsentType]
    if consent_type not in valid_types:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid consent type: {consent_type}. Valid: {valid_types}")

    result = await db.execute(
        select(ConsentLog).where(
            ConsentLog.user_id == current_user.id,
            ConsentLog.client_id == current_user.client_id,
            ConsentLog.consent_type == consent_type,
            ConsentLog.withdrawn_at.is_(None),
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Active consent not found")

    record.consented = False
    record.withdrawn_at = datetime.now(timezone.utc)
    ip = request.client.host if request.client else "unknown"
    ua = request.headers.get("user-agent", "unknown")
    record.ip_address = ip
    record.user_agent = ua

    await AuditService.log_action(
        db, client_id=current_user.client_id,
        action="CONSENT_WITHDRAWN",
        user_id=current_user.id,
        table_name="consent_logs",
        record_id=record.id,
        new_values={"consent_type": consent_type, "withdrawn": True},
        ip_address=ip,
        user_agent=ua,
    )
    await db.commit()
    await db.refresh(record)
    return record


@router.get("/history", response_model=List[ConsentResponse])
async def get_consent_history(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    result = await db.execute(
        select(ConsentLog)
        .where(ConsentLog.user_id == current_user.id, ConsentLog.client_id == current_user.client_id)
        .order_by(ConsentLog.timestamp.desc())
    )
    return result.scalars().all()
