import os
import uuid
import logging
import re
import json
from datetime import datetime
from typing import Optional, Dict, Any
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, Inches
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.pv import PV
from app.models.meeting import Meeting
from app.models.action import Action
from app.models.setting import BrandingSettings

logger = logging.getLogger(__name__)

class DOCXService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def generate_pv_docx(self, pv_id: str, client_id: str, branding_id: Optional[str] = None, language: str = "fr") -> str:
        """
        Generates a PV as a DOCX file and returns the file path.
        Includes on-the-fly translation via Mistral if languages mismatch.
        """
        # 0. Localization Strings
        LOCALES = {
            "ar": {
                "title": "محضر اجتماع",
                "date": "التاريخ",
                "location": "المكان",
                "duration": "المدة (دقيقة)",
                "participants": "المشاركون",
                "agenda": "جدول الأعمال",
                "discussion": "ملخص المناقشات",
                "decisions": "القرارات",
                "actions": "خطة العمل",
                "task": "المهمة",
                "assignee": "المسؤول",
                "due_date": "الموعد النهائي",
                "signature": "الاعتماد",
                "director": "المدير العام",
            },
            "fr": {
                "title": "Procès-Verbal",
                "date": "Date",
                "location": "Lieu",
                "duration": "Durée (min)",
                "participants": "Participants",
                "agenda": "Ordre du Jour",
                "discussion": "Résumé des Discussions",
                "decisions": "Décisions",
                "actions": "Plan d'Action",
                "task": "Tâche",
                "assignee": "Responsable",
                "due_date": "Échéance",
                "signature": "Approbation (Signature)",
                "director": "Directeur Général (DG)",
            },
            "en": {
                "title": "Meeting Minutes",
                "date": "Date",
                "location": "Location",
                "duration": "Duration (min)",
                "participants": "Participants",
                "agenda": "Agenda",
                "discussion": "Discussion Summary",
                "decisions": "Decisions",
                "actions": "Action Items",
                "task": "Task",
                "assignee": "Assignee",
                "due_date": "Due Date",
                "signature": "Approval (Signature)",
                "director": "General Manager (DG)",
            }
        }
        
        strings = LOCALES.get(language, LOCALES["fr"])
        is_rtl = (language == "ar")
        alignment = WD_ALIGN_PARAGRAPH.RIGHT if is_rtl else WD_ALIGN_PARAGRAPH.LEFT

        # 1. Load Data
        stmt = (
            select(PV)
            .options(
                selectinload(PV.meeting).selectinload(Meeting.participants),
                selectinload(PV.meeting).selectinload(Meeting.agendas),
                selectinload(PV.sections),
            )
            .where(PV.id == pv_id)
            .where(PV.client_id == client_id)
        )
        result = await self.db.execute(stmt)
        pv_obj = result.scalar_one_or_none()

        if not pv_obj:
            raise HTTPException(status_code=404, detail="PV not found")

        from app.models.action import Assignment
        action_stmt = (
            select(Action)
            .options(selectinload(Action.assignments).selectinload(Assignment.user))
            .where(Action.meeting_id == pv_obj.meeting_id)
            .where(Action.client_id == client_id)
        )
        action_result = await self.db.execute(action_stmt)
        actions = action_result.scalars().all()

        # 0. Localization Strings
        LOCALES = {
            "ar": {"not_assigned": "غير محدد"},
            "fr": {"not_assigned": "Non défini"},
            "en": {"not_assigned": "N/A"}
        }
        strings = LOCALES.get(language, LOCALES["fr"])

        # 2. Translation Logic
        display_title = pv_obj.title
        display_discussion = pv_obj.content_html
        display_decisions = [s.content for s in pv_obj.sections if s.type == "decision"]
        display_actions = []
        for a in actions:
            assignee_name = strings["not_assigned"]
            if a.assignments and len(a.assignments) > 0:
                assignment = a.assignments[0]
                if assignment.user and assignment.user.full_name:
                    assignee_name = assignment.user.full_name
                elif assignment.external_name:
                    assignee_name = assignment.external_name
                    
            display_actions.append({
                "description": a.title,
                "assignee": assignee_name,
                "due_date": a.due_date.strftime("%Y-%m-%d") if a.due_date else datetime.now().strftime("%Y-%m-%d")
            })

        from app.services.pv_service import PVService, TranslationError
        if pv_obj.language != language:
            logger.info(f"Language mismatch in DOCX export. Translating content to {language}...")
            content_to_translate = {
                "title": display_title,
                "summary": display_discussion,
                "decisions": display_decisions,
                "actions": display_actions
            }
            try:
                translated = await PVService.translate_content(content_to_translate, language)
                display_title = translated.get("title", display_title)
                display_discussion = translated.get("summary", display_discussion)
                display_decisions = translated.get("decisions", display_decisions)
                display_actions = translated.get("actions", display_actions)
            except TranslationError as e:
                logger.error(f"Translation failed for DOCX pv_id={pv_id}: {e}")
                raise HTTPException(
                    status_code=502,
                    detail="AI translation service failed. Please try again later.",
                )


        # 3. Create Document
        doc = Document()
        
        # Title
        title_para = doc.add_heading(strings["title"], 0)
        title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        p_pv_title = doc.add_paragraph(display_title)
        p_pv_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_pv_title.runs[0].bold = True

        doc.add_paragraph("_" * 50).alignment = WD_ALIGN_PARAGRAPH.CENTER

        # Meta info
        start_time = pv_obj.meeting.start_time
        date_str = start_time.strftime("%Y-%m-%d") if start_time else "N/A"
        
        meta = doc.add_paragraph()
        meta.alignment = alignment
        meta.add_run(f"{strings['date']}: ").bold = True
        meta.add_run(f"{date_str}\t")
        meta.add_run(f"{strings['location']}: ").bold = True
        meta.add_run(f"{pv_obj.meeting.location or 'N/A'}")

        # Participants
        p_part = doc.add_paragraph()
        p_part.alignment = alignment
        p_part.add_run(f"{strings['participants']}: ").bold = True
        p_part.add_run(", ".join([p.name or p.email for p in pv_obj.meeting.participants]))

        # Agenda
        doc.add_heading(strings["agenda"], level=1).alignment = alignment
        for a in sorted(pv_obj.meeting.agendas, key=lambda x: x.order):
            p = doc.add_paragraph(a.title, style='List Bullet')
            p.alignment = alignment

        # Discussion
        doc.add_heading(strings["discussion"], level=1).alignment = alignment
        clean_text = re.sub('<[^<]+?>', '', display_discussion or "")
        p_disc = doc.add_paragraph(clean_text)
        p_disc.alignment = alignment

        # Decisions
        if display_decisions:
            doc.add_heading(strings["decisions"], level=1).alignment = alignment
            for d in display_decisions:
                p = doc.add_paragraph(d, style='List Bullet')
                p.alignment = alignment

        # Actions
        if display_actions:
            doc.add_heading(strings["actions"], level=1).alignment = alignment
            table = doc.add_table(rows=1, cols=3)
            table.style = 'Table Grid'
            hdr_cells = table.rows[0].cells
            hdr_cells[0].text = strings["task"]
            hdr_cells[1].text = strings["assignee"]
            hdr_cells[2].text = strings["due_date"]
            
            for action in display_actions:
                row_cells = table.add_row().cells
                row_cells[0].text = action.get("description", "N/A")
                row_cells[1].text = action.get("assignee", "N/A")
                row_cells[2].text = action.get("due_date", "N/A")

        # Signature
        doc.add_paragraph("\n" * 3)
        sig = doc.add_paragraph(f"{strings['signature']}:")
        sig.alignment = WD_ALIGN_PARAGRAPH.LEFT if is_rtl else WD_ALIGN_PARAGRAPH.RIGHT
        doc.add_paragraph("___________________________").alignment = sig.alignment
        doc.add_paragraph(strings["director"]).alignment = sig.alignment

        # Save
        filename = f"pv_{pv_id}_{uuid.uuid4().hex[:8]}.docx"
        filepath = f"/tmp/{filename}"
        doc.save(filepath)
        
        return filepath
