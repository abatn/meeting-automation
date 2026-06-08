from typing import Any, List
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from pydantic import BaseModel

from app.api import deps
from app.models.meeting import Meeting as MeetingModel
from app.models.meeting import Participant as ParticipantModel
from app.models.recording import Recording as RecordingModel
from app.models.transcription import Transcription as TranscriptionModel
from app.models.pv import PV as PVModel, Section as SectionModel
from app.models.action import Action as ActionModel
from app.models.user import User as UserModel
from app.models.user import UserRole, UserStatus
from app.schemas.meeting import Meeting, MeetingCreate, MeetingWithPV
from app.schemas.user import User
from app.services.meeting_service import MeetingService


class RecordingStatus(BaseModel):
    """Recording status with real-time duration calculation"""
    is_recording: bool
    recording_duration: int  # Duration in seconds
    recording_id: str | None = None

router = APIRouter()


@router.get("/users", response_model=List[User])
async def list_client_users(
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """
    Retrieve all active users for the current client to populate the participant dropdown.
    """
    result = await db.execute(
        select(UserModel)
        .where(UserModel.client_id == current_user.client_id)
        .where(UserModel.status == UserStatus.ACTIVE.value)
    )
    return result.scalars().all()


@router.get("/", response_model=List[MeetingWithPV])
async def read_meetings(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """
    Retrieve meetings.
    """
    result = await db.execute(
        select(MeetingModel)
        .where(MeetingModel.client_id == current_user.client_id)
        .options(
            selectinload(MeetingModel.participants), 
            selectinload(MeetingModel.agendas),
            selectinload(MeetingModel.pv)
        )
        .order_by(MeetingModel.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    meetings = result.scalars().all()
    return meetings


@router.get("/my-meetings", response_model=List[MeetingWithPV])
async def list_my_meetings(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """
    Retrieve a list of meetings the current user is a participant in.
    """
    result = await db.execute(
        select(MeetingModel)
        .where(MeetingModel.client_id == current_user.client_id)
        .options(
            selectinload(MeetingModel.participants), 
            selectinload(MeetingModel.agendas),
            selectinload(MeetingModel.pv)
        )
        .join(ParticipantModel, MeetingModel.id == ParticipantModel.meeting_id)
        .where(ParticipantModel.user_id == current_user.id)
        .order_by(MeetingModel.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    meetings = result.scalars().all()
    return meetings


@router.get("/team-meetings", response_model=List[MeetingWithPV])
async def list_team_meetings(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """
    Retrieve a list of meetings where users managed by the current user are participants.
    Accessible only by managers.
    """
    if current_user.role != UserRole.MANAGER and current_user.role != UserRole.DG:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough privileges to access team meetings",
        )

    managed_user_ids = [report.id for report in current_user.reports]

    if not managed_user_ids:
        return []  # No reports, no team meetings

    result = await db.execute(
        select(MeetingModel)
        .where(MeetingModel.client_id == current_user.client_id)
        .options(
            selectinload(MeetingModel.participants), 
            selectinload(MeetingModel.agendas),
            selectinload(MeetingModel.pv)
        )
        .join(ParticipantModel, MeetingModel.id == ParticipantModel.meeting_id)
        .where(ParticipantModel.user_id.in_(managed_user_ids))
        .order_by(MeetingModel.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    meetings = result.scalars().all()
    return meetings


@router.post("/", response_model=Meeting, status_code=status.HTTP_201_CREATED)
async def create_meeting(
    *,
    db: AsyncSession = Depends(deps.get_db),
    meeting_in: MeetingCreate,
    current_user: UserModel = Depends(deps.get_current_user),
    meeting_service: MeetingService = Depends(deps.get_meeting_service),
) -> Any:
    """
    Create new meeting.
    """
    meeting = await meeting_service.create_meeting(
        meeting_in=meeting_in, owner_id=current_user.id, client_id=current_user.client_id
    )
    return meeting


@router.get("/{meeting_id}", response_model=Meeting)
async def get_meeting(
    meeting_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_user),
    meeting_service: MeetingService = Depends(deps.get_meeting_service),
) -> Any:
    """
    Get meeting by ID.
    """
    meeting = await meeting_service.get_meeting(meeting_id, current_user.client_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return meeting


@router.get("/{meeting_id}/recording-status", response_model=RecordingStatus)
async def get_recording_status(
    meeting_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """
    Get recording status with real-time duration calculation.
    This endpoint allows all participants to see the same recording duration
    synchronized from the server.
    """
    # Verify meeting belongs to current client
    result = await db.execute(
        select(MeetingModel).where(
            MeetingModel.id == meeting_id,
            MeetingModel.client_id == current_user.client_id,
        )
    )
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    # Get the active recording for this meeting
    recording_result = await db.execute(
        select(RecordingModel).where(
            RecordingModel.meeting_id == meeting_id,
            RecordingModel.client_id == current_user.client_id,
            RecordingModel.status.in_(["recording", "streaming"]),
        )
    )
    recording = recording_result.scalar_one_or_none()

    if not recording:
        # No active recording
        return RecordingStatus(
            is_recording=False,
            recording_duration=0,
            recording_id=None,
        )

    # Calculate duration from creation time
    now = datetime.now(timezone.utc)
    duration_seconds = int((now - recording.created_at).total_seconds())

    return RecordingStatus(
        is_recording=True,
        recording_duration=duration_seconds,
        recording_id=recording.id,
    )


@router.get("/{meeting_id}/ai-insights")
async def get_ai_insights(
    meeting_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """
    Returns pipeline results (transcription, PV sections, actions) for the meeting.
    Used by the frontend MeetingRoom to drive the recording state machine
    (idle -> recording -> processing -> completed/failed).

    Returns:
        - status: "idle" | "recording" | "processing" | "completed" | "failed"
        - recording_id, file_size, duration, format
        - transcription: {id, status, language, full_text, segments}
        - pv: {id, status, title, language, sections: [{order, type, title, content}]}
        - actions: [{id, title, description, priority, status, assigned_to}]
        - insights: derived from PV sections for UI display

    Tier 4.1 (UX): Provides real backend state so the UI doesn't stay stuck on
    "Processing insights..." when the pipeline has actually completed.
    """
    # Verify meeting belongs to current client (multi-tenant isolation)
    meeting_res = await db.execute(
        select(MeetingModel).where(
            MeetingModel.id == meeting_id,
            MeetingModel.client_id == current_user.client_id,
        )
    )
    meeting = meeting_res.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    # Latest recording (any status)
    rec_res = await db.execute(
        select(RecordingModel)
        .where(
            RecordingModel.meeting_id == meeting_id,
            RecordingModel.client_id == current_user.client_id,
        )
        .order_by(RecordingModel.created_at.desc())
        .limit(1)
    )
    recording = rec_res.scalar_one_or_none()

    # Default response: no recording yet
    if not recording:
        return {
            "status": "idle",
            "recording_id": None,
            "file_size": None,
            "duration": None,
            "format": None,
            "transcription": None,
            "pv": None,
            "actions": [],
            "insights": [],
        }

    # Map recording.status -> frontend status
    # Backend states: "streaming" | "uploaded" | "transcribing" | "analyzing" | "completed" | "failed"
    # Frontend states: "idle" | "recording" | "processing" | "completed" | "failed"
    status_map = {
        "streaming": "recording",
        "uploaded": "processing",
        "transcribing": "processing",
        "analyzing": "processing",
        "completed": "completed",
        "failed": "failed",
    }
    frontend_status = status_map.get(recording.status, "processing")

    # Transcription (may not exist yet)
    trans_res = await db.execute(
        select(TranscriptionModel).where(
            TranscriptionModel.recording_id == recording.id,
            TranscriptionModel.client_id == current_user.client_id,
        )
    )
    transcription = trans_res.scalar_one_or_none()
    transcription_payload = None
    if transcription:
        transcription_payload = {
            "id": transcription.id,
            "status": transcription.status,
            "language": transcription.language or "auto",
            "full_text": transcription.full_text,
            "segments": transcription.segments or [],
        }

    # PV (may not exist yet)
    pv_payload = None
    pv_res = await db.execute(
        select(PVModel).where(
            PVModel.meeting_id == meeting_id,
            PVModel.client_id == current_user.client_id,
        )
    )
    pv = pv_res.scalar_one_or_none()
    if pv:
        sec_res = await db.execute(
            select(SectionModel)
            .where(SectionModel.pv_id == pv.id)
            .order_by(SectionModel.order)
        )
        sections = sec_res.scalars().all()
        pv_payload = {
            "id": pv.id,
            "status": pv.status,
            "title": pv.title,
            "language": pv.language,
            "content_html": pv.content_html,
            "sections": [
                {
                    "order": s.order,
                    "type": s.type,
                    "title": s.title,
                    "content": s.content,
                }
                for s in sections
            ],
        }

    # Actions
    actions_payload = []
    act_res = await db.execute(
        select(ActionModel)
        .where(
            ActionModel.meeting_id == meeting_id,
            ActionModel.client_id == current_user.client_id,
        )
        .options(selectinload(ActionModel.assignments).selectinload(__import__("app.models.action", fromlist=["Assignment"]).Assignment.user))
    )
    for a in act_res.scalars().all():
        assigned_to = None
        assigned_user_id = None
        if a.assignments:
            first = a.assignments[0]
            assigned_user_id = first.user_id
            if first.user:
                assigned_to = first.user.full_name or first.user.email
            else:
                assigned_to = first.external_name or first.external_email
        actions_payload.append({
            "id": a.id,
            "title": a.title,
            "description": a.description,
            "priority": a.priority,
            "status": a.status.value if hasattr(a.status, "value") else str(a.status),
            "due_date": a.due_date.isoformat() if a.due_date else None,
            "assigned_to": assigned_to,
            "assigned_user_id": assigned_user_id,
        })

    # Derive AI insights from PV sections (simple heuristic for UI display)
    insights = []
    if pv_payload and pv_payload.get("sections"):
        for sec in pv_payload["sections"]:
            if sec.get("type") in ("summary", "decision", "action") and sec.get("content"):
                content_preview = (sec["content"] or "")[:160]
                if len(sec["content"]) > 160:
                    content_preview += "..."
                insights.append({
                    "topic": sec.get("title", "Insight"),
                    "confidence": 0.85,
                    "actions": [content_preview],
                })

    return {
        "status": frontend_status,
        "recording_id": recording.id,
        "file_size": recording.file_size,
        "duration": recording.duration,
        "format": recording.format,
        "transcription": transcription_payload,
        "pv": pv_payload,
        "actions": actions_payload,
        "insights": insights,
    }


@router.patch("/{meeting_id}/cancel", response_model=Meeting)
async def cancel_meeting(
    meeting_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_user),
    meeting_service: MeetingService = Depends(deps.get_meeting_service),
) -> Any:
    """
    Cancel a planned meeting (Soft Delete).
    """
    from app.schemas.meeting import MeetingUpdate
    from app.models.meeting import MeetingStatus
    
    meeting = await meeting_service.get_meeting(meeting_id, current_user.client_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
        
    if meeting.status != MeetingStatus.PLANNED:
        raise HTTPException(status_code=400, detail="Only planned meetings can be cancelled")

    update_data = MeetingUpdate(status=MeetingStatus.CANCELLED)
    # P2-3: Pass current_user_id for authorization check
    updated_meeting = await meeting_service.update_meeting(meeting_id, current_user.client_id, update_data, current_user_id=current_user.id)
    
    return updated_meeting


@router.delete("/{meeting_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_meeting(
    meeting_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_user),
    meeting_service: MeetingService = Depends(deps.get_meeting_service),
):
    """
    Delete a meeting.
    """
    success = await meeting_service.delete_meeting(meeting_id, current_user.client_id)
    if not success:
        raise HTTPException(status_code=404, detail="Meeting not found")
