# OnlyOffice PDF Edit & Save Pipeline

## Flow Overview

```
Frontend (Edit Online Button)
    ↓ GET /api/v1/pv/{pv_id}/onlyoffice/config
Backend: Generates DOCX → Uploads to S3
    ↓ Returns OnlyOffice config (JWT token)
OnlyOffice Editor (iframe)
    ↓ User edits document
    ↓ Forcesave / Final Save → Callback
Backend Callback: /api/v1/pv/{pv_id}/onlyoffice/callback
    ↓ Downloads edited DOCX from OnlyOffice
    ↓ Uploads DOCX to S3 (pv_exports/{pv_id}/edited_document.docx)
    ↓ Deletes old PDF (cache-busting)
    ↓ Creates PVVersion (ISO 27001 audit)
    ↓ Background: Converts DOCX → PDF via OnlyOffice converter
    ↓ Uploads PDF to S3 (pv_exports/{pv_id}/final_document.pdf)
Frontend: Download PDF/DOCX buttons
    ↓ GET /api/v1/pv/{pv_id}/pdf?language=X
    ↓ Returns PDF from S3 (waits for conversion if in-progress)
```

## Step-by-Step

### 1. Frontend → PVValidator.tsx
- **File**: `frontend/src/components/meetings/PVValidator.tsx`
- **Button**: "Edit Online" (line 163-174)
- **Action**: Opens `/editor/{pvId}?lang={language}` in new tab
- **Component**: `OnlyOfficeEditor.tsx`

### 2. Frontend → OnlyOfficeEditor.tsx
- **File**: `frontend/src/components/meetings/OnlyOfficeEditor.tsx`
- **Flow**:
  1. Fetches config from `GET /api/v1/pv/{pvId}/onlyoffice/config`
  2. Loads OnlyOffice DocsAPI script
  3. Creates `DocsAPI.DocEditor` in iframe
- **Editor Container**: `onlyoffice-editor-container`

### 3. Backend → OnlyOffice Config (pv.py:329-347)
- **File**: `backend/app/api/v1/pv.py`
- **Endpoint**: `GET /{pv_id}/onlyoffice/config`
- **Process**:
  1. Generate DOCX via `DOCXService.generate_pv_docx()`
  2. Upload DOCX to S3: `tmp_edits/{pv_id}/{filename}.docx`
  3. Create OnlyOffice config with:
     - `download_url` → backend endpoint to serve DOCX from S3
     - `callback_url` → backend endpoint for save notifications
     - `forcesave: true` → auto-save while editing
  4. Sign config with JWT (`ONLYOFFICE_SECRET`)

### 4. OnlyOffice → Callback (pv.py:359-430)
- **Endpoint**: `POST /{pv_id}/onlyoffice/callback`
- **Status codes**:
  - `2` → Ready for saving (final save)
  - `6` → Forcesave (auto-save while editing)
- **Process**:
  1. Verify JWT token from callback
  2. Download edited DOCX from OnlyOffice
  3. Upload DOCX to S3: `pv_exports/{pv_id}/edited_document.docx`
  4. Set Redis key: `pdf_converting_{pv_id}` = "true" (sync state)
  5. Delete old PDF from S3 (cache-busting)
  6. Create `PVVersion` record (ISO 27001 audit trail)
  7. Trigger background PDF conversion: `run_pdf_conversion()`

### 5. Background → PDF Conversion (pv.py:36-110)
- **Function**: `run_pdf_conversion(pv_id, docx_key, pdf_key)`
- **Process**:
  1. Call OnlyOffice converter: `http://onlyoffice/converter`
  2. Source: DOCX from S3 via backend download URL
  3. Convert to PDF
  4. Download PDF from converter response
  5. Upload PDF to S3: `pv_exports/{pv_id}/final_document.pdf`
  6. Delete Redis key: `pdf_converting_{pv_id}`
  7. Delete DOCX from S3 (cleanup)

### 6. Frontend → Download PDF/DOCX
- **File**: `frontend/src/components/meetings/DocumentExportMenu.tsx`
- **Buttons**: PDF + Word (DOCX)
- **API**: `GET /api/v1/pv/{pv_id}/{format}?language={language}`
- **Process**:
  - PDF: Checks Redis for conversion status, waits if in-progress
  - DOCX: Downloads directly from S3
  - Returns file as blob for browser download

## Key Files

| Layer | File | Purpose |
|-------|------|---------|
| Frontend | `frontend/src/components/meetings/PVValidator.tsx` | Edit Online button |
| Frontend | `frontend/src/components/meetings/OnlyOfficeEditor.tsx` | OnlyOffice iframe editor |
| Frontend | `frontend/src/components/meetings/DocumentExportMenu.tsx` | PDF/DOCX download buttons |
| Frontend | `frontend/src/services/onlyoffice.ts` | OnlyOffice API service |
| Frontend | `frontend/src/pages/OnlyOfficePage.tsx` | Editor page wrapper |
| Backend API | `backend/app/api/v1/pv.py` | OnlyOffice endpoints (config, callback, download) |
| Backend Service | `backend/app/services/docx_service.py` | DOCX generation |
| Backend Config | `backend/app/core/config.py` | ONLYOFFICE_SECRET, ONLYOFFICE_URL |

## S3 Storage Structure

```
recordings/
tmp_edits/{pv_id}/
  └── {filename}.docx          ← Temporary DOCX for OnlyOffice editing
pv_exports/{pv_id}/
  ├── edited_document.docx     ← Edited DOCX from OnlyOffice
  └── final_document.pdf       ← Converted PDF from OnlyOffice
```

## Config Values

| Variable | Value | Purpose |
|----------|-------|---------|
| `ONLYOFFICE_SECRET` | `super_secret_jwt_key_onlyoffice_2026` | JWT signing for config/callback |
| `ONLYOFFICE_URL` | `http://localhost:8080` | Public OnlyOffice URL |
| `ONLYOFFICE_BACKEND_URL` | `http://backend:8000` | Internal backend URL |
| `PUBLIC_BACKEND_URL` | External URL | For OnlyOffice callbacks |

## ISO 27001 Compliance

- Every OnlyOffice save creates a `PVVersion` record
- Version includes: snapshot_data, change_summary, created_by_id
- Change messages: "Edited via OnlyOffice Online (Forcesave)" or "(Final Save)"

## Status
- ✅ OnlyOffice container running (port 8081 → 80)
- ✅ Callback endpoint working
- ✅ Background PDF conversion implemented
- ✅ Redis sync-state for conversion tracking
- ✅ Versioning/audit trail implemented
