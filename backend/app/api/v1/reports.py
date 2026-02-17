from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from backend.app.api import deps
from backend.app.services.report_generator_service import ReportGeneratorService
from backend.app.services.meeting_service import meeting_service
from backend.app.models.user import User
import io

router = APIRouter()

@router.get("/meetings/{meeting_id}/export-pdf", summary="Export meeting report as PDF")
async def export_meeting_report_pdf(
    meeting_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user)
):
    meeting = await meeting_service.get_meeting_by_id(db, meeting_id)

    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    # Basic authorization check (can be expanded)
    if meeting.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to export this meeting's report")

    # Prepare data for the report
    meeting_data = {
        "title": meeting.title,
        "date": meeting.created_at.strftime("%Y-%m-%d") if meeting.created_at else "N/A",
        "time": meeting.created_at.strftime("%H:%M:%S") if meeting.created_at else "N/A",
        "transcription": meeting.transcription.content if meeting.transcription else "No transcription available.",
        "decisions": [decision.content for decision in meeting.decisions] if meeting.decisions else [],
        "action_points": [action.description for action in meeting.actions] if meeting.actions else [],
    }

    report_generator = ReportGeneratorService()
    pdf_buffer = report_generator.generate_meeting_report_pdf(meeting_data)

    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=meeting_report_{meeting_id}.pdf"}
    )