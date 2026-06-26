# OnlyOffice PDF Edit & Save Pipeline

## Flow Overview (AKTUELL — Phase 73)

```
Frontend (Edit Online Button)
    ↓ GET /api/v1/pv/{pv_id}/onlyoffice/config
Backend: Generates DOCX → Uploads to S3
    ↓ Returns OnlyOffice config (JWT token, documentType: "word")
OnlyOffice Editor (iframe via Socket.IO /doc/)
    ↓ User edits document
    ↓ Forcesave / Final Save → Callback
Backend Callback: /api/v1/pv/{pv_id}/onlyoffice/callback
    ↓ Downloads edited DOCX from OnlyOffice (https → http Fix)
    ↓ Uploads DOCX to S3 (pv_exports/{pv_id}/edited_document.docx)
    ↓ Deletes old PDF (cache-busting)
    ↓ Creates PVVersion (ISO 27001 audit)
    ↓ Triggers SYNCHRONOUS PDF conversion (Phase 73)
    ↓ Converts DOCX → PDF via OnlyOffice converter (0.09s)
    ↓ Uploads PDF to S3 (pv_exports/{pv_id}/final_document.pdf)
Frontend: Download PDF/DOCX buttons
    ↓ GET /api/v1/pv/{pv_id}/pdf?language=X
    ↓ Synchron: Konvertiert wenn nötig, liefert sofort PDF (2.2s)
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
- **Socket.IO**: Verbindung über `/doc/` Pfad (nicht `/socket.io/`)

### 3. Backend → OnlyOffice Config (pv.py:329-353)
- **File**: `backend/app/api/v1/pv.py`
- **Endpoint**: `GET /{pv_id}/onlyoffice/config`
- **Process**:
  1. Generate DOCX via `DOCXService.generate_pv_docx()`
  2. Upload DOCX to S3: `tmp_edits/{pv_id}/{filename}.docx`
  3. Create OnlyOffice config with:
     - `documentType: "word"` (Phase 64 — ohne dieses lädt OnlyOffice Spreadsheet-Editor)
     - `download_url` → backend endpoint to serve DOCX from S3
     - `callback_url` → backend endpoint for save notifications
     - `forcesave: true` → auto-save while editing
  4. Sign config with JWT (`ONLYOFFICE_SECRET`)

### 4. OnlyOffice → Callback (pv.py:390-465)
- **Endpoint**: `POST /{pv_id}/onlyoffice/callback`
- **Status codes**:
  - `1` → Editing (Auto-Save, Phase 69)
  - `2` → Ready for saving (final save)
  - `6` → Forcesave (auto-save while editing)
- **Process**:
  1. Verify JWT token from callback
  2. Download edited DOCX from OnlyOffice (https → http URL-Mapping, Phase 71)
  3. Upload DOCX to S3: `pv_exports/{pv_id}/edited_document.docx`
  4. Set Redis key: `pdf_converting_{pv_id}` = "true" (sync state)
  5. Delete old PDF from S3 (cache-busting)
  6. Create `PVVersion` record (ISO 27001 audit trail)
  7. Trigger background PDF conversion: `run_pdf_conversion()`

### 5. PDF Conversion (pv.py:34-110)
- **Function**: `run_pdf_conversion(pv_id, docx_key, pdf_key)`
- **Process**:
  1. Call OnlyOffice converter: `http://onlyoffice-staging:80/converter`
  2. Source: DOCX from S3 via backend download URL
  3. Convert to PDF (0.09s — Converter ist schnell)
  4. Download PDF from converter response (https → http URL-Mapping, Phase 71)
  5. Upload PDF to S3: `pv_exports/{pv_id}/final_document.pdf`
  6. Delete Redis key: `pdf_converting_{pv_id}`

### 6. Frontend → Download PDF/DOCX
- **File**: `frontend/src/components/meetings/DocumentExportMenu.tsx`
- **Buttons**: PDF + Word (DOCX)
- **API**: `GET /api/v1/pv/{pv_id}/{format}?language={language}`
- **Process** (Phase 73 — synchron):
  - PDF: Prüft S3 → Wenn PDF aktuell → liefert es (2.2s)
  - PDF: Wenn PDF nicht vorhanden → SYNCHRON Konvertierung → liefert PDF
  - DOCX: Download directly from S3

## Fixes (Phases 64-73)

| Phase | Problem | Fix |
|-------|---------|-----|
| 64 | `documentType: "word"` fehlte → Spreadsheet-Editor geladen | `pv.py:349` hinzugefügt |
| 64 | Socket.IO `/doc/` nicht geproxied → SPA HTML statt Handshake | Frontend nginx `location /doc/` hinzugefügt |
| 65 | WebSocket-Header fehlten → `upgrade=undefined` | `ds-docservice.conf` 3 Proxy-Locations mit Headers |
| 66 | Hardcoded `onlyoffice` Hostname → DNS-Fehler | `settings.ONLYOFFICE_URL` statt hardcoded |
| 67 | Callback Hostname hardcoded | `pass` (URL bereits korrekt) |
| 68 | Forcesave nicht aktiviert | ConfigMap + Editor-Config `forcesave: True` |
| 69 | Callback status 1 ignoriert | `status in [1, 2, 6]` |
| 70 | EBUSY: local.json gesperrt | ConfigMap-Mount entfernt |
| 71 | Converter gibt `https://` zurück → timeout | URL-Mapping `https→http` |
| 72 | Image-Mismatch (altes Image ohne Fix) | korrekter Image-Name `meeting-automation-backend:latest` |
| 73 | Background-Task ging verloren → 50s Timeout | Synchroner Aufruf (`await run_pdf_conversion`) |

## Key Files

| Layer | File | Purpose |
|-------|------|---------|
| Frontend | `frontend/src/components/meetings/PVValidator.tsx` | Edit Online button |
| Frontend | `frontend/src/components/meetings/OnlyOfficeEditor.tsx` | OnlyOffice iframe editor |
| Frontend | `frontend/src/components/meetings/DocumentExportMenu.tsx` | PDF/DOCX download buttons |
| Frontend | `frontend/src/services/onlyoffice.ts` | OnlyOffice API service |
| Frontend | `frontend/src/pages/OnlyOfficePage.tsx` | Editor page wrapper |
| Backend API | `backend/app/api/v1/pv.py` | OnlyOffice endpoints (config, callback, download, conversion) |
| Backend Service | `backend/app/services/docx_service.py` | DOCX generation |
| Backend Config | `backend/app/core/config.py` | ONLYOFFICE_SECRET, ONLYOFFICE_URL |
| K8s ConfigMap | `onlyoffice-ds-docservice` | nginx WebSocket-Header |
| K8s ConfigMap | `frontend-nginx-config` | Socket.IO `/doc/` Proxy |

## S3 Storage Structure

```
recordings/
tmp_edits/{pv_id}/
  └── {filename}.docx          ← Temporary DOCX for OnlyOffice editing
pv_exports/{pv_id}/
  ├── edited_document.docx     ← Edited DOCX from OnlyOffice (40-41KB)
  └── final_document.pdf       ← Converted PDF from OnlyOffice (140-145KB)
```

## Config Values

| Variable | Value | Purpose |
|----------|-------|---------|
| `ONLYOFFICE_SECRET` | `staging-onlyoffice-secret-jwt-key-2026` | JWT signing for config/callback |
| `ONLYOFFICE_URL` | `http://onlyoffice-staging:80` | Internal OnlyOffice URL |
| `ONLYOFFICE_BACKEND_URL` | `http://backend:8000` | Internal backend URL |
| `PUBLIC_BACKEND_URL` | `https://staging.meeting-automation.com` | For OnlyOffice callbacks |

## Performance

| Metric | Wert |
|--------|------|
| Converter Speed | 0.09s (DOCX → PDF) |
| PDF Download (mit Konvertierung) | 2.2s |
| DOCX Download | sofort |
| S3 Upload PDF | 0.01s |

## ISO 27001 Compliance

- Every OnlyOffice save creates a `PVVersion` record
- Version includes: snapshot_data, change_summary, created_by_id
- Change messages: "Edited via OnlyOffice Online (Forcesave)" or "(Final Save)"

## Status
- ✅ OnlyOffice container running (port 80)
- ✅ Socket.IO WebSocket via `/doc/` Pfad
- ✅ Callback endpoint working (status 1, 2, 6)
- ✅ PDF conversion synchron (0.09s)
- ✅ Redis sync-state for conversion tracking
- ✅ Versioning/audit trail implemented
- ✅ HTTPS → HTTP URL-Mapping für Converter
- ✅ forcesave: True via Editor-Config
