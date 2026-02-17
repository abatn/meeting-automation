import logging
from datetime import datetime
from typing import Optional
from docx import Document
from docx.shared import Inches

from fastapi import HTTPException, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.core.config import settings
from backend.app.models.meeting import Meeting
from backend.app.models.pv import PV, PVStatus
from backend.app.models.transcription import Transcription
from backend.app.models.user import User, UserRole
from backend.app.schemas.pv import PVCreate, PVUpdate
from backend.app.services.mistral_client import MistralClient, MOCK_PV_RESPONSE
from backend.app.utils.storage import storage_service
from sqlalchemy.orm import selectinload

# For PDF generation
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from io import BytesIO

logger = logging.getLogger(__name__)


mistral_client = MistralClient()

async def generate_pv(meeting_id: int, transcription_id: Optional[int] = None, template: Optional[str] = None, db: AsyncSession = Depends(), current_user: Optional[User] = None):
    """
    Generates a PV for a meeting using Mistral AI.
    """
    result = await db.execute(select(Meeting).filter(Meeting.id == meeting_id))
    meeting = result.scalars().first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    transcription: Optional[Transcription] = None
    if transcription_id:
        result = await db.execute(select(Transcription).filter(Transcription.id == transcription_id))
        transcription = result.scalars().first()
        if not transcription:
            raise HTTPException(status_code=404, detail="Transcription not found")
    else:
        result = await db.execute(select(Transcription).filter(Transcription.meeting_id == meeting_id))
        transcription = result.scalars().first()
        if not transcription:
            raise HTTPException(status_code=400, detail="No transcription found for this meeting. Please provide a transcription_id.")

    if not transcription.content:
        raise HTTPException(status_code=400, detail="Transcription content is empty.")

    try:
        pv_content = await mistral_client.generate_pv(transcription.content)

        if not pv_content:
            raise HTTPException(status_code=500, detail="Mistral API returned empty content for PV generation.")

        pv_create_data = {
            "content": pv_content,
            "meeting_id": meeting_id,
            "generated_by_id": current_user.id if current_user else None # Add generated_by_id
        }

        try:
            pv = PV(**pv_create_data, created_at=datetime.now(), updated_at=datetime.now())
            db.add(pv)
            await db.commit()
            await db.refresh(pv)

            return pv
        except Exception as e:
            await db.rollback()
            logger.error(f"Error creating PV: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to create PV: {e}")
    except Exception as e:
        logger.error(f"Error generating PV: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate PV: {e}")


async def get_pv_by_id(pv_id: int, db: AsyncSession = Depends(), current_user: Optional[User] = None):
    """
    Retrieves a PV by its ID, with eager loading for related objects.
    """
    result = await db.execute(
        select(PV)
        .filter(PV.id == pv_id)
            .options(selectinload(PV.meeting), selectinload(PV.validator), selectinload(PV.generator))
    )
    pv = result.scalars().first()
    if not pv:
        raise HTTPException(status_code=404, detail="PV not found")
    return pv


async def get_pv_by_meeting(meeting_id: int, db: AsyncSession = Depends(), current_user: Optional[User] = None):
    """
    Retrieves a PV by its meeting ID, with eager loading for related objects.
    """
    result = await db.execute(
        select(PV)
        .filter(PV.meeting_id == meeting_id)
        .options(selectinload(PV.meeting), selectinload(PV.validator), selectinload(PV.generator))
    )
    pv = result.scalars().first()
    if not pv:
        raise HTTPException(status_code=404, detail="PV not found for this meeting")
    return pv


async def update_pv(pv_id: int, pv_update: PVUpdate, db: AsyncSession = Depends(), current_user: Optional[User] = None):
    """
    Updates a PV manually.
    """
    result = await db.execute(select(PV).filter(PV.id == pv_id))
    pv = result.scalars().first()
    if not pv:
        raise HTTPException(status_code=404, detail="PV not found")

    update_data = pv_update.dict(exclude_unset=True)
    if "decisions" in update_data:
        pv.decisions = update_data["decisions"]
    if "action_points" in update_data:
        pv.action_points = update_data["action_points"]
    if "title" in update_data:
        pv.title = update_data["title"]
    if "content" in update_data:
        pv.content = update_data["content"]

    pv.updated_at = datetime.now()
    try:
        db.add(pv)
        await db.commit()
        await db.refresh(pv)
        return pv
    except Exception as e:
        await db.rollback()
        logger.error(f"Error updating PV: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update PV: {e}")


async def validate_pv(pv_id: int, user: User, db: AsyncSession = Depends(), comment: Optional[str] = None):
    """
    Validates a PV (DG-Freigabe).
    """
    user = await db.merge(user)
    result = await db.execute(select(PV).filter(PV.id == pv_id))
    pv = result.scalars().first()
    if not pv:
        raise HTTPException(status_code=404, detail="PV not found")

    logger.info(f"PV {pv_id} current status: {pv.status}")
    user_id = user.id
    logger.info(f"User {user_id} with role {user.role} attempting to validate PV {pv_id}")

    if user.role != UserRole.DG:
        logger.warning(f"User {user_id} with role {user.role} attempting to validate PV {pv_id} but is not a DG.")
        raise HTTPException(status_code=403, detail="Only DGs can validate PVs")

    # Check if PV is already validated or rejected
    if pv.status == PVStatus.VALIDATED:
        raise HTTPException(status_code=400, detail="PV is already validated.")
    if pv.status == PVStatus.REJECTED:
        raise HTTPException(status_code=400, detail="PV has been rejected and cannot be validated.")

    pv.validated_at = datetime.now()
    pv.validator = user
    pv.validation_comment = comment
    pv.status = PVStatus.VALIDATED  # Set status to VALIDATED upon successful validation
    logger.info(f"Attempting to validate PV {pv_id} by user {user_id} with role {user.role}")
    try:
        db.add(pv)
        await db.commit()
        await db.refresh(pv, attribute_names=["validator", "generator"])
        logger.info(f"PV {pv_id} successfully validated by user {user_id}. New status: {pv.status}")
        return pv
    except Exception as e:
        await db.rollback()
        logger.error(f"Error validating PV {pv_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to validate PV: {e}. Details: {str(e)}")


async def delete_pv(pv_id: int, db: AsyncSession = Depends(), current_user: Optional[User] = None):
    """
    Deletes a PV (Admin only).
    """
    result = await db.execute(select(PV).filter(PV.id == pv_id))
    pv = result.scalars().first()
    if not pv:
        raise HTTPException(status_code=404, detail="PV not found")

    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Only Admins can delete PVs")

    try:
        await db.delete(pv)
        await db.commit()
        return {"message": "PV deleted successfully"}
    except Exception as e:
        await db.rollback()
        logger.error(f"Error deleting PV: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete PV: {e}")


async def extract_decisions(pv_content: str) -> str:
    """
    Extracts decisions from PV content using Mistral AI.
    """
    try:
        decisions_content = await mistral_client.extract_decisions(pv_content)
        if not decisions_content:
            logger.error("Mistral API returned empty content for decision extraction.")
            raise HTTPException(status_code=500, detail="Mistral API returned empty content for decision extraction.")
        return decisions_content
    except Exception as e:
        logger.error(f"Error extracting decisions from PV: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to extract decisions: {e}. Details: {e}")


async def extract_action_points(pv_content: str) -> str:
    """
    Extracts action points from PV content using Mistral AI.
    """
    try:
        action_points_content = await mistral_client.extract_action_points(pv_content)
        if not action_points_content:
            raise HTTPException(status_code=500, detail="Mistral API returned empty content for action points extraction.")
        return action_points_content
    except Exception as e:
        logger.error(f"Error extracting action points from PV: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to extract action points: {e}")


async def generate_summary_from_pv(pv_content: str) -> str:
    """
    Generates a summary from PV content using Mistral AI.
    """
    try:
        summary_content = await mistral_client.generate_summary(pv_content)
        if not summary_content:
            raise HTTPException(status_code=500, detail="Mistral API returned empty content for summary generation.")
        return summary_content
    except Exception as e:
        logger.error(f"Error generating summary from PV: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate summary: {e}")


async def generate_pv_pdf(pv_id: int, db: AsyncSession = Depends(), current_user: Optional[User] = None):
    """
    Generates a PDF from a PV.
    """
    result = await db.execute(select(PV).filter(PV.id == pv_id))
    pv = result.scalars().first()
    if not pv:
        raise HTTPException(status_code=404, detail="PV not found")

    result = await db.execute(select(Meeting).filter(Meeting.id == pv.meeting_id))
    meeting = result.scalars().first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found for this PV")

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph(f"<h1>Procès-verbal</h1>", styles['h1']))
    story.append(Paragraph(f"<h2>{meeting.title}</h2>", styles['h2']))
    story.append(Paragraph(pv.content, styles['Normal']))

    doc.build(story)
    buffer.seek(0)

    return StreamingResponse(buffer, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename=pv_{pv_id}.pdf"})


async def generate_pv_docx(pv_id: int, db: AsyncSession = Depends(), current_user: Optional[User] = None):
    """
    Generates a Word document from a PV.
    """
    result = await db.execute(select(PV).filter(PV.id == pv_id))
    pv = result.scalars().first()
    if not pv:
        raise HTTPException(status_code=404, detail="PV not found")

    result = await db.execute(select(Meeting).filter(Meeting.id == pv.meeting_id))
    meeting = result.scalars().first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found for this PV")

    document = Document()
    document.add_heading('Procès-verbal', level=1)
    document.add_heading(meeting.title, level=2)
    document.add_paragraph(pv.content)

    # Save the document to a BytesIO object
    from io import BytesIO
    file_stream = BytesIO()
    document.save(file_stream)
    file_stream.seek(0)

    return StreamingResponse(file_stream, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", headers={"Content-Disposition": f"attachment; filename=pv_{pv_id}.docx"})