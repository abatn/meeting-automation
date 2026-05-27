# Plan: OnlyOffice PDF in PV Validate → Email Pipeline

## Problem

**Aktuelle Situation:**
```
n8n pv-validated workflow
    ↓ GET /api/v1/reports/automation/pdf/{meeting_id}
    ↓ reports.py:160 → pdf_service.generate_pv_pdf()
    ↓ Generiert PDF aus HTML (Datenbank-Inhalt)
    ↓ ❌ IGNORIERT das OnlyOffice-bearbeitete PDF!
```

**Das OnlyOffice PDF existiert bereits:**
```
S3: pv_exports/{pv_id}/final_document.pdf  ← Nur dieses wird NICHT verwendet!
```

**Der /pv/{pv_id}/pdf Endpoint (pv.py:122-211) hat bereits die richtige Logik:**
1. Prüft S3 auf `pv_exports/{pv_id}/final_document.pdf`
2. Wenn vorhanden → served das OnlyOffice PDF
3. Wenn nicht → Fallback auf HTML→PDF Generation

## Lösung

### Option A: reports.py Endpoint erweitern (Empfohlen)

**Änderung in `backend/app/api/v1/reports.py` (Zeile 139-162):**

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
    """
    from app.models.pv import PV as PVModel
    from fastapi import HTTPException
    import boto3
    from app.core.config import settings

    pv_stmt = select(PVModel).where(PVModel.meeting_id == meeting_id)
    pv_res = await db.execute(pv_stmt)
    pv = pv_res.scalars().first()
    if not pv:
        raise HTTPException(status_code=404, detail="PV not found for this meeting")

    # 1. Prüfe ob OnlyOffice PDF in S3 existiert
    s3 = boto3.client("s3",
        endpoint_url=settings.S3_ENDPOINT,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
    )
    pdf_key = f"pv_exports/{pv.id}/final_document.pdf"
    
    try:
        s3.head_object(Bucket=settings.S3_BUCKET_NAME, Key=pdf_key)
        # OnlyOffice PDF existiert → herunterladen und zurückgeben
        local_pdf_path = f"/tmp/automation_{pv.id}.pdf"
        s3.download_file(settings.S3_BUCKET_NAME, pdf_key, local_pdf_path)
        return FileResponse(path=local_pdf_path, filename=f"Protocol_{meeting_id}.pdf")
    except:
        # 2. Fallback: PDF aus HTML generieren
        from app.services.pdf_service import PDFService
        pdf_service = PDFService(db)
        pdf_path = await pdf_service.generate_pv_pdf(pv_id=pv.id, client_id=pv.client_id)
        return FileResponse(path=pdf_path, filename=f"Protocol_{meeting_id}.pdf")
```

### Option B: Code-Duplikation vermeiden

**Bessere Variante:** Gemeinsame Helper-Funktion erstellen:

```python
# backend/app/services/pdf_download_service.py
async def get_pv_pdf_file(pv_id: str, db: AsyncSession, client_id: str) -> str:
    """
    Returns path to PDF file. Prefers OnlyOffice-edited PDF from S3.
    Falls back to HTML→PDF generation.
    """
    # 1. Check S3 for OnlyOffice PDF
    s3 = boto3.client(...)
    pdf_key = f"pv_exports/{pv_id}/final_document.pdf"
    try:
        s3.head_object(Bucket=settings.S3_BUCKET_NAME, Key=pdf_key)
        local_path = f"/tmp/{pv_id}_{uuid4().hex[:6]}.pdf"
        s3.download_file(settings.S3_BUCKET_NAME, pdf_key, local_path)
        return local_path
    except:
        pass
    
    # 2. Fallback: Generate from HTML
    pdf_service = PDFService(db)
    return await pdf_service.generate_pv_pdf(pv_id=pv_id, client_id=client_id)
```

**Dann beide Endpoints nutzen diese Funktion:**
- `pv.py:122` → `download_pv_pdf`
- `reports.py:139` → `get_meeting_pdf_for_automation`

## Dateien zu ändern

| Datei | Änderung |
|-------|----------|
| `backend/app/api/v1/reports.py` | Endpoint erweitern: S3-Check vor PDF-Generation |
| Optional: `backend/app/services/pdf_download_service.py` | Neue Helper-Service für beide Endpoints |

## Test-Szenarien

| Szenario | Erwartetes Ergebnis |
|----------|-------------------|
| PV wurde in OnlyOffice bearbeitet | n8n lädt `pv_exports/{pv_id}/final_document.pdf` aus S3 |
| PV wurde NICHT in OnlyOffice bearbeitet | n8n generiert PDF aus HTML (wie bisher) |
| PDF Conversion läuft noch | n8n wartet oder bekommt Fallback-PDF |
| S3 nicht erreichbar | Fallback auf HTML→PDF Generation |

## Impact

- ✅ **n8n pv-validated workflow** sendet das OnlyOffice-bearbeitete PDF
- ✅ **Keine Breaking Changes** - Fallback bleibt erhalten
- ✅ **ISO 27001** - Audit-Log bleibt unverändert
- ✅ **Multi-Tenant** - client_id Filterung bleibt erhalten
