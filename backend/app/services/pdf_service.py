import os
import uuid
import logging
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
from app.models.pv import PV

logger = logging.getLogger(__name__)

class PDFService:
    def __init__(self, db: AsyncSession, s3_client=None):
        self.db = db
        # Fallback auf mock-client, falls keine S3 credentials existieren
        try:
            self.s3 = s3_client or boto3.client(
                's3',
                endpoint_url=settings.MINIO_URL if hasattr(settings, 'MINIO_URL') else 'http://localhost:9000',
                aws_access_key_id=settings.MINIO_USER if hasattr(settings, 'MINIO_USER') else 'minioadmin',
                aws_secret_access_key=settings.MINIO_PASSWORD if hasattr(settings, 'MINIO_PASSWORD') else 'minioadmin'
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
        self.bucket_name = getattr(settings, 'MINIO_PDF_BUCKET', 'meeting-pdfs')

    async def generate_pv_pdf(self, pv_id: int) -> str:
        """Hauptmethode: Generiert PDF und gibt Dateipfad zurück"""
        # In einer echten Implementierung würden wir hier prüfen, ob das PDF schon in Minio ist.
        # Für diese Demo generieren wir es direkt neu oder geben einen lokalen Pfad zurück.
        
        # 1. HTML rendern
        html_content = await self._render_pv_html(pv_id)
        
        # 2. PDF generieren
        pdf_filename = f"pv_{pv_id}_{uuid.uuid4().hex[:8]}.pdf"
        pdf_path = f"/tmp/{pdf_filename}"
        
        await self._convert_html_to_pdf(html_content, pdf_path)
        
        # 3. Optional: In Minio hochladen (hier auskommentiert um Fehler ohne S3 zu vermeiden)
        # s3_url = await self._upload_to_minio(pdf_path, pdf_filename)
        
        return pdf_path

    async def _render_pv_html(self, pv_id: int) -> str:
        """PV-Daten laden und HTML rendern"""
        # Mock-Daten, in echt würde man das PV und die Relationen (Actions, Meeting) aus der DB laden
        pv_data = {
            "title": "اجتماع استراتيجية تكنولوجيا المعلومات (IT Strategy)",
            "date": "2026-02-23",
            "location": "قاعة الاجتماعات الرئيسية / Microsoft Teams",
            "duration": "45",
            "participants": ["أحمد بن علي (المدير العام)", "سارة محمد (مديرة المشروع)", "يوسف عبد الله (مطور)"],
            "agenda": """1. مراجعة ميزانية الربع الأول
2. خطة التوظيف""",
            "discussion": "<p>تمت مناقشة الميزانية وتمت الموافقة على زيادة ميزانية التدريب بنسبة 15%.</p>",
            "decisions": ["الموافقة على ميزانية التدريب", "البدء في تعيين 3 مطورين جدد"],
            "actions": [
                {"description": "إعداد وصف وظيفي للمطورين", "assignee": "سارة محمد", "due_date": "2026-03-01"},
                {"description": "التواصل مع قسم المالية", "assignee": "أحمد بن علي", "due_date": "2026-02-28"}
            ]
        }
        
        try:
            template = self.template_env.get_template('pv_template.html')
            return template.render(pv=pv_data)
        except Exception as e:
            logger.error(f"Error rendering template: {e}")
            raise HTTPException(status_code=500, detail="Could not render PDF template")

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
            logger.error(f"Error generating PDF with WeasyPrint: {e}")
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
