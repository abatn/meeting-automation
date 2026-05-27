# Implementation Plan: PDF Download mit S3-Prüfung

## Ziel
`/api/v1/reports/automation/pdf/{meeting_id}` erweitern, um zuerst S3 zu prüfen, dann Fallback auf WeasyPrint.

## Logik

```
1. Prüfe S3: pv_exports/{pv_id}/final_document.pdf
   → Existiert? → Sende es ✅
   → Nein? → Gehe zu Schritt 2

2. Generiere PDF aus DB-HTML via WeasyPrint
   → Sende es ✅
```

## Änderungen

### Datei: `backend/app/api/v1/reports.py`

**Aktuell (Zeile 139-162):**
```python
@router.get("/automation/pdf/{meeting_id}")
async def get_meeting_pdf_for_automation(
    meeting_id: str,
    db: AsyncSession = Depends(deps.get_db),
    api_key_valid: bool = Depends(deps.verify_internal_api_key),
) -> Any:
    """Returns the PV PDF for n8n attachment."""
    from app.models.pv import PV as PVModel
    from fastapi.responses import FileResponse
    from app.services.pdf_service import PDFService

    pv_stmt = select(PVModel).where(PVModel.meeting_id == meeting_id)
    pv_res = await db.execute(pv_stmt)
    pv = pv_res.scalars().first()
    if not pv:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="PV not found for this meeting")

    pdf_service = PDFService(db)
    pdf_path = await pdf_service.generate_pv_pdf(pv_id=pv.id, client_id=pv.client_id)
    
    return FileResponse(path=pdf_path, filename=f"Protocol_{meeting_id}.pdf")
```

**Neu:**
```python
@router.get("/automation/pdf/{meeting_id}")
async def get_meeting_pdf_for_automation(
    meeting_id: str,
    db: AsyncSession = Depends(deps.get_db),
    api_key_valid: bool = Depends(deps.verify_internal_api_key),
) -> Any:
    """
    Returns the PV PDF for n8n attachment.
    Prefers OnlyOffice-edited PDF from S3 if available.
    Falls back to WeasyPrint generation from DB-HTML.
    """
    from app.models.pv import PV as PVModel
    from fastapi.responses import FileResponse
    from fastapi import HTTPException
    from app.services.pdf_service import PDFService
    from app.core.config import settings
    import boto3

    pv_stmt = select(PVModel).where(PVModel.meeting_id == meeting_id)
    pv_res = await db.execute(pv_stmt)
    pv = pv_res.scalars().first()
    if not pv:
        raise HTTPException(status_code=404, detail="PV not found for this meeting")

    # Schritt 1: Prüfe S3 auf OnlyOffice PDF
    pdf_key = f"pv_exports/{pv.id}/final_document.pdf"
    s3 = boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
    )
    
    try:
        s3.head_object(Bucket=settings.S3_BUCKET_NAME, Key=pdf_key)
        # OnlyOffice PDF existiert → aus S3 laden
        local_pdf_path = f"/tmp/automation_{pv.id}.pdf"
        s3.download_file(settings.S3_BUCKET_NAME, pdf_key, local_pdf_path)
        return FileResponse(path=local_pdf_path, filename=f"Protocol_{meeting_id}.pdf")
    except Exception:
        pass  # S3 nicht verfügbar oder PDF nicht vorhanden → Fallback

    # Schritt 2: Generiere PDF aus DB-HTML via WeasyPrint
    pdf_service = PDFService(db)
    pdf_path = await pdf_service.generate_pv_pdf(pv_id=pv.id, client_id=pv.client_id)
    return FileResponse(path=pdf_path, filename=f"Protocol_{meeting_id}.pdf")
```

## Test-Szenarien

| Szenario | Erwartetes Ergebnis |
|----------|-------------------|
| PV in OnlyOffice bearbeitet | ✅ Sendet OnlyOffice PDF aus S3 |
| PV NICHT bearbeitet | ✅ Sendet WeasyPrint PDF aus DB |
| S3 ausgefallen | ✅ Fallback auf WeasyPrint |
| MinIO gelöscht | ✅ Fallback auf WeasyPrint |

## Impact

- ✅ **n8n pv-validated workflow** sendet das OnlyOffice-bearbeitete PDF (falls vorhanden)
- ✅ **Keine Breaking Changes** - Fallback bleibt erhalten
- ✅ **ISO 27001** - Audit-Log bleibt unverändert
- ✅ **Multi-Tenant** - client_id Filterung bleibt erhalten
- ✅ **Resilient** - Funktioniert auch bei S3-Ausfall

## Dateien zu ändern

| Datei | Änderung |
|-------|----------|
| `backend/app/api/v1/reports.py` | S3-Check vor WeasyPrint einfügen |

## Status
- [ ] Implementierung
- [ ] Test: PV mit OnlyOffice PDF → S3 PDF gesendet
- [ ] Test: PV ohne OnlyOffice PDF → WeasyPrint PDF gesendet
- [ ] Test: S3 ausfällt → WeasyPrint Fallback
