import os
import uuid
import logging
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

    async def generate_pv_docx(self, pv_id: str, branding_id: Optional[str] = None, language: str = "ar") -> str:
        """
        Generates a PV as a DOCX file and returns the file path.
        """
        # 0. Localization
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
                "actions": "خطة العمل (Action Items)",
                "task": "المهمة",
                "assignee": "المسؤول",
                "due_date": "الموعد النهائي",
                "signature": "الاعتماد (التوقيع الإلكتروني)",
                "director": "المدير العام (DG)",
                "page": "صفحة",
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
                "page": "Page",
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
                "page": "Page",
            }
        }
        
        strings = LOCALES.get(language, LOCALES["ar"])
        is_rtl = (language == "ar")

        # 1. Load Data
        stmt = (
            select(PV)
            .options(
                selectinload(PV.meeting).selectinload(Meeting.participants),
                selectinload(PV.meeting).selectinload(Meeting.agendas),
                selectinload(PV.sections),
            )
            .where(PV.id == pv_id)
        )
        result = await self.db.execute(stmt)
        pv_obj = result.scalar_one_or_none()

        if not pv_obj:
            raise HTTPException(status_code=404, detail="PV not found")

        action_stmt = select(Action).where(Action.meeting_id == pv_obj.meeting_id)
        action_result = await self.db.execute(action_stmt)
        actions = action_result.scalars().all()

        # 2. Create DOCX
        doc = Document()
        
        # Alignment setting
        alignment = WD_ALIGN_PARAGRAPH.RIGHT if is_rtl else WD_ALIGN_PARAGRAPH.LEFT

        # Header
        h1 = doc.add_heading(strings["title"], 0)
        h1.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        p_title = doc.add_paragraph(pv_obj.title)
        p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_title.runs[0].bold = True

        doc.add_paragraph("_" * 50).alignment = WD_ALIGN_PARAGRAPH.CENTER

        # Meta Info
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
        agendas = sorted(pv_obj.meeting.agendas, key=lambda x: x.order)
        for a in agendas:
            p = doc.add_paragraph(a.title, style='List Bullet')
            p.alignment = alignment

        # Discussion
        doc.add_heading(strings["discussion"], level=1).alignment = alignment
        # Simple text for now, could be improved to parse HTML
        disc_text = pv_obj.content_html or "N/A"
        import re
        clean_text = re.sub('<[^<]+?>', '', disc_text) # Strip HTML tags
        p_disc = doc.add_paragraph(clean_text)
        p_disc.alignment = alignment

        # Decisions
        decisions = [s.content for s in pv_obj.sections if s.type == "decision"]
        if decisions:
            doc.add_heading(strings["decisions"], level=1).alignment = alignment
            for d in decisions:
                p = doc.add_paragraph(d, style='List Bullet')
                p.alignment = alignment

        # Actions
        if actions:
            doc.add_heading(strings["actions"], level=1).alignment = alignment
            table = doc.add_table(rows=1, cols=3)
            table.style = 'Table Grid'
            hdr_cells = table.rows[0].cells
            hdr_cells[0].text = strings["task"]
            hdr_cells[1].text = strings["assignee"]
            hdr_cells[2].text = strings["due_date"]
            
            for action in actions:
                row_cells = table.add_row().cells
                row_cells[0].text = action.title
                row_cells[1].text = action.description.split("Assigned to: ")[-1] if "Assigned to: " in action.description else "N/A"
                row_cells[2].text = action.due_date.strftime("%Y-%m-%d") if action.due_date else "N/A"

        # Footer / Signature
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
