import os
import uuid
import logging
import traceback
from typing import Optional
import jinja2
import boto3
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

# Versuche WeasyPrint zu importieren (kann je nach System libs erfordern)
try:
    from weasyprint import HTML, CSS
    WEASYPRINT_AVAILABLE = True
except (ImportError, OSError):
    logging.warning("WeasyPrint is not installed or missing system dependencies. PDF generation will mock if called.")
    WEASYPRINT_AVAILABLE = False

from app.core.config import settings
from app.models.pv import PV, Section
from app.models.meeting import Meeting, Participant, Agenda
from app.models.action import Action
from sqlalchemy import select
from sqlalchemy.orm import selectinload

logger = logging.getLogger(__name__)

class PDFService:
    def __init__(self, db: AsyncSession, s3_client=None):
        self.db = db
        # Fallback auf mock-client, falls keine S3 credentials existieren
        try:
            self.s3 = s3_client or boto3.client(
                's3',
                endpoint_url=getattr(settings, 'S3_ENDPOINT', 'http://localhost:9000'),
                aws_access_key_id=getattr(settings, 'S3_ACCESS_KEY', 'minioadmin'),
                aws_secret_access_key=getattr(settings, 'S3_SECRET_KEY', 'minioadmin')
            )
        except Exception as e:
            logger.warning(f"Could not initialize S3 client: {e}")
            self.s3 = None
            
        # Jinja2 Setup für das HTML Template
        template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates')
        self.template_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(template_dir),
            autoescape=True
        )
        self.bucket_name = getattr(settings, 'S3_BUCKET_NAME', 'meeting-pdfs')

    async def generate_pv_pdf(self, pv_id: str) -> str:
        """Hauptmethode: Generiert PDF und gibt Dateipfad zurück"""
        # 1. Daten aus DB laden (Echt-Daten)
        stmt = (
            select(PV)
            .options(
                selectinload(PV.meeting).selectinload(Meeting.participants),
                selectinload(PV.meeting).selectinload(Meeting.agendas),
                selectinload(PV.sections)
            )
            .where(PV.id == pv_id)
        )
        result = await self.db.execute(stmt)
        pv_obj = result.scalar_one_or_none()
        
        if not pv_obj:
            raise HTTPException(status_code=404, detail="PV not found")
            
        # Action items separat laden
        action_stmt = select(Action).where(Action.meeting_id == pv_obj.meeting_id)
        action_result = await self.db.execute(action_stmt)
        actions = action_result.scalars().all()

        # 2. Template-Daten aufbereiten
        pv_data = {
            "title": pv_obj.title or pv_obj.meeting.title,
            "date": (pv_obj.meeting.start_time.strftime("%Y-%m-%d") if pv_obj.meeting.start_time else "N/A"),
            "location": pv_obj.meeting.location or "N/A",
            "duration": str(int((pv_obj.meeting.end_time - pv_obj.meeting.start_time).total_seconds() / 60)) if pv_obj.meeting.end_time else "N/A",
            "participants": [p.name or p.email for p in pv_obj.meeting.participants],
            "agenda": "\n".join([a.title for a in sorted(pv_obj.meeting.agendas, key=lambda x: x.order)]),
            "discussion": pv_obj.content_html or "N/A",
            "decisions": [s.content for s in pv_obj.sections if s.type == "decision"],
            "actions": [
                {
                    "description": a.title, 
                    "assignee": a.description.split("Assigned to: ")[-1] if "Assigned to: " in a.description else "N/A", 
                    "due_date": a.due_date.strftime("%Y-%m-%d") if a.due_date else "N/A"
                } for a in actions
            ]
        }

        # 3. HTML rendern
        try:
            template = self.template_env.get_template('pv_template.html')
            html_content = template.render(pv=pv_data)
        except Exception as e:
            logger.error(f"Error rendering template: {e}")
            raise HTTPException(status_code=500, detail="Could not render PDF template")
        
        # 4. PDF generieren
        pdf_filename = f"pv_{pv_id}_{uuid.uuid4().hex[:8]}.pdf"
        pdf_path = f"/tmp/{pdf_filename}"
        
        await self._convert_html_to_pdf(html_content, pdf_path)
        
        return pdf_path

    async def _convert_html_to_pdf(self, html: str, filepath: str) -> str:
        """HTML zu PDF konvertieren mit WeasyPrint"""
        if not WEASYPRINT_AVAILABLE:
            # Erstelle ein Dummy-PDF, falls WeasyPrint nicht verfügbar ist
            with open(filepath, "wb") as f:
                f.write(b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj
3 0 obj
<<
/Type /Page
/Parent 2 0 R
/Resources <<
/Font <<
/F1 4 0 R
>>
>>
/MediaBox [0 0 612 792]
/Contents 5 0 R
>>
endobj
4 0 obj
<<
/Type /Font
/Subtype /Type1
/BaseFont /Helvetica
>>
endobj
5 0 obj
<<
/Length 44
>>
stream
BT
/F1 24 Tf
100 700 Td
(WeasyPrint not installed) Tj
ET
endstream
endobj
xref
0 6
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000219 00000 n
0000000307 00000 n
trailer
<<
/Size 6
/Root 1 0 R
>>
startxref
402
%%EOF""")
            return filepath
            
        try:
            HTML(string=html).write_pdf(filepath)
            return filepath
        except Exception as e:
            logger.error(f"Error generating PDF with WeasyPrint: {e}\n{traceback.format_exc()}")
            raise HTTPException(status_code=500, detail="Error generating PDF file")

    async def _upload_to_minio(self, file_path: str, object_name: str) -> str:
        """PDF in Minio speichern"""
        if not self.s3:
            return ""
        try:
            self.s3.upload_file(file_path, self.bucket_name, object_name)
            url = self.s3.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': object_name},
                ExpiresIn=3600
            )
            return url
        except Exception as e:
            logger.error(f"S3 Upload failed: {e}")
            return ""

    async def get_pdf_from_minio(self, pv_id: int) -> Optional[bytes]:
        """Bestehendes PDF aus Minio holen"""
        # Implementierung für produktiven Einsatz
        pass
