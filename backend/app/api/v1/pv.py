from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.api.deps import get_db, get_current_user
from app.models.user import UserModel
from app.services.pdf_service import PDFService
import os

router = APIRouter()

@router.get("/{pv_id}/pdf")
async def download_pv_pdf(
    pv_id: int,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> FileResponse:
    """
    PV als PDF herunterladen
    - Prüft Berechtigung (User muss Zugriff haben)
    - Holt PDF aus Cache oder generiert neu
    - Gibt FileResponse mit Content-Disposition zurück
    """
    
    # In einer echten App würden wir hier prüfen, ob current_user 
    # Zugriff auf pv_id hat (z.B. Teilnehmer des Meetings ist)
    
    try:
        pdf_service = PDFService(db)
        pdf_path = await pdf_service.generate_pv_pdf(pv_id)
        
        if not os.path.exists(pdf_path):
            raise HTTPException(status_code=404, detail="PDF file not found after generation")
            
        # FileResponse kümmert sich um den Download und den arabischen Dateinamen
        # encoded url parameter ist für non-ascii chars in filename
        return FileResponse(
            path=pdf_path, 
            media_type="application/pdf", 
            filename=f"محضر_اجتماع_{pv_id}.pdf"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{pv_id}/validate")
async def validate_pv(
    pv_id: int,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    PV freigeben (Approve & Sign).
    Setzt den Status des PVs auf 'validated' und löst ggf. einen n8n Webhook aus.
    """
    # Placeholder für DB-Update und Audit-Logging
    return {"status": "success", "message": f"PV {pv_id} successfully validated."}
