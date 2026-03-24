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
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.pv import PV
from app.models.meeting import Meeting
from app.models.meeting_room import MeetingRoom
from app.models.action import Action
from app.models.setting import BrandingSettings

logger = logging.getLogger(__name__)

class DOCXService:
    def __init__(self, db: AsyncSession):
        self.db = db

    def _set_rtl(self, p):
        """
        Applies RTL formatting to a paragraph and all its current runs.
        Ensures both paragraph direction and run-level complex script settings.
        """
        # 1. Paragraph-level RTL
        pPr = p._element.get_or_add_pPr()
        bidi = pPr.xpath('./w:bidi')
        if not bidi:
            bidi_el = OxmlElement('w:bidi')
            bidi_el.set(qn('w:val'), '1')
            pPr.append(bidi_el)
        
        # Set alignment to right for RTL
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        
        # 2. Run-level RTL (for existing runs)
        for run in p.runs:
            rPr = run._element.get_or_add_rPr()
            
            # w:rtl for right-to-left text direction
            rtl = rPr.xpath('./w:rtl')
            if not rtl:
                rtl_el = OxmlElement('w:rtl')
                rtl_el.set(qn('w:val'), '1')
                rPr.append(rtl_el)
                
            # w:cs for complex script (Arabic) support
            cs = rPr.xpath('./w:cs')
            if not cs:
                cs_el = OxmlElement('w:cs')
                cs_el.set(qn('w:val'), '1')
                rPr.append(cs_el)

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
                "duration": "المدة",
                "minutes": "دقيقة",
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
                "not_assigned": "غير محدد",
            },
            "fr": {
                "title": "Procès-Verbal",
                "date": "Date",
                "location": "Lieu",
                "duration": "Durée",
                "minutes": "min",
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
                "not_assigned": "Non défini",
            },
            "en": {
                "title": "Meeting Minutes",
                "date": "Date",
                "location": "Location",
                "duration": "Duration",
                "minutes": "min",
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
                "not_assigned": "N/A",
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
                selectinload(PV.meeting).selectinload(Meeting.room),
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
        # Check if stored PV language matches the requested export language
        if pv_obj.language != language:
            logger.info(f"Translating DOCX content from {pv_obj.language} to {language} via Mistral...")
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
                logger.error(f"Mistral translation failed for DOCX: {e}. Falling back to original.")

        # 3. Create Document
        doc = Document()
        
        # Force Document-wide RTL for Arabic in Section Properties
        if is_rtl:
            for section in doc.sections:
                sectPr = section._sectPr
                bidi = sectPr.xpath('./w:bidi')
                if not bidi:
                    bidi_el = OxmlElement('w:bidi')
                    bidi_el.set(qn('w:val'), '1')
                    sectPr.append(bidi_el)

        # Title
        title_para = doc.add_heading(strings["title"], 0)
        title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        if is_rtl: self._set_rtl(title_para)
        
        p_pv_title = doc.add_paragraph(display_title)
        p_pv_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        if is_rtl: self._set_rtl(p_pv_title)
        if p_pv_title.runs:
            p_pv_title.runs[0].bold = True

        sep = doc.add_paragraph("_" * 50)
        sep.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # Meta info
        start_time = pv_obj.meeting.start_time
        end_time = pv_obj.meeting.end_time
        date_str = start_time.strftime("%Y-%m-%d") if start_time else "N/A"
        duration_val = "N/A"
        if start_time and end_time:
            duration_val = str(int((end_time - start_time).total_seconds() / 60))

        meta = doc.add_paragraph()
        meta.alignment = alignment
        meta.add_run(f"{strings['date']}: ").bold = True
        meta.add_run(f"{date_str}\t")
        meta.add_run(f"{strings['duration']}: ").bold = True
        meta.add_run(f"{duration_val} {strings['minutes']}\t")
        meta.add_run(f"{strings['location']}: ").bold = True

        # Location logic
        display_location = "N/A"
        if pv_obj.meeting.room:
            display_location = pv_obj.meeting.room.name
        elif pv_obj.meeting.location:
            display_location = pv_obj.meeting.location
            
        meta.add_run(f"{display_location}")
        if is_rtl: self._set_rtl(meta)

        # Participants
        p_part = doc.add_paragraph()
        p_part.alignment = alignment
        p_part.add_run(f"{strings['participants']}: ").bold = True
        p_part.add_run(", ".join([p.name or p.email for p in pv_obj.meeting.participants]))
        if is_rtl: self._set_rtl(p_part)

        # Agenda
        h_agenda = doc.add_heading(strings["agenda"], level=1)
        h_agenda.alignment = alignment
        if is_rtl: self._set_rtl(h_agenda)
        for a in sorted(pv_obj.meeting.agendas, key=lambda x: x.order):
            p = doc.add_paragraph(a.title, style='List Bullet')
            p.alignment = alignment
            if is_rtl: self._set_rtl(p)

        # Discussion
        h_disc = doc.add_heading(strings["discussion"], level=1)
        h_disc.alignment = alignment
        if is_rtl: self._set_rtl(h_disc)
        clean_text = re.sub('<[^<]+?>', '', display_discussion or "")
        p_disc = doc.add_paragraph(clean_text)
        p_disc.alignment = alignment
        if is_rtl: self._set_rtl(p_disc)

        # Decisions
        if display_decisions:
            h_dec = doc.add_heading(strings["decisions"], level=1)
            h_dec.alignment = alignment
            if is_rtl: self._set_rtl(h_dec)
            for d in display_decisions:
                p = doc.add_paragraph(d, style='List Bullet')
                p.alignment = alignment
                if is_rtl: self._set_rtl(p)

        # Actions
        if display_actions:
            h_act = doc.add_heading(strings["actions"], level=1)
            h_act.alignment = alignment
            if is_rtl: self._set_rtl(h_act)
            table = doc.add_table(rows=1, cols=3)
            table.style = 'Table Grid'
            
            # Force table to be Visual RTL
            if is_rtl:
                tblPr = table._element.xpath('w:tblPr')[0]
                bidiVisual = tblPr.xpath('./w:bidiVisual')
                if not bidiVisual:
                    bidiVisual_el = OxmlElement('w:bidiVisual')
                    tblPr.append(bidiVisual_el)

            hdr_cells = table.rows[0].cells
            hdr_cells[0].text = strings["task"]
            hdr_cells[1].text = strings["assignee"]
            hdr_cells[2].text = strings["due_date"]
            
            if is_rtl:
                for cell in hdr_cells:
                    for p in cell.paragraphs:
                        self._set_rtl(p)

            for action in display_actions:
                row_cells = table.add_row().cells
                row_cells[0].text = str(action.get("description", "N/A"))
                row_cells[1].text = str(action.get("assignee", "N/A"))
                row_cells[2].text = str(action.get("due_date", "N/A"))
                if is_rtl:
                    for cell in row_cells:
                        for p in cell.paragraphs:
                            self._set_rtl(p)

        # Signature
        doc.add_paragraph("\n" * 3)
        # For RTL, we'll keep it consistent with the overall alignment.
        sig_alignment = alignment
        
        sig = doc.add_paragraph(f"{strings['signature']}:")
        sig.alignment = sig_alignment
        if is_rtl: self._set_rtl(sig)
        
        line = doc.add_paragraph("___________________________")
        line.alignment = sig_alignment
        if is_rtl: self._set_rtl(line)
        
        dir_p = doc.add_paragraph(strings["director"])
        dir_p.alignment = sig_alignment
        if is_rtl: self._set_rtl(dir_p)

        # 4. Metadata: Add meeting duration to Core Properties
        if duration_val != "N/A":
            doc.core_properties.comments = f"Meeting Duration: {duration_val} minutes"
            doc.core_properties.subject = f"PV for {pv_obj.title} - Duration: {duration_val} min"

        # Save
        filename = f"pv_{pv_id}_{uuid.uuid4().hex[:8]}.docx"
        filepath = f"/tmp/{filename}"
        doc.save(filepath)
        
        return filepath
