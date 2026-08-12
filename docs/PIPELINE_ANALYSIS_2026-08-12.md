# Pipeline-Analyse: Meeting erstellen → Aufnahme → PV editieren

**Erstellt:** 2026-08-12
**Status:** Vollständig analysiert

---

## 1. Pipeline-Übersicht

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    MEETING AUTOMATION PIPELINE                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                   │
│  │   1. Meeting  │    │  2. LiveKit   │    │  3. Egress   │                   │
│  │   Erstellen   │───▶│   Room +     │───▶│  Recording   │                   │
│  │              │    │   Audio      │    │   (WebM)     │                   │
│  └──────────────┘    └──────────────┘    └──────────────┘                   │
│         │                    │                    │                           │
│         ▼                    ▼                    ▼                           │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                   │
│  │  n8n Webhook │    │  Participants │    │  MinIO/S3    │                   │
│  │  triggern    │    │  beitreten    │    │  Upload      │                   │
│  └──────────────┘    └──────────────┘    └──────────────┘                   │
│                                               │                              │
│                                               ▼                              │
│                                      ┌──────────────┐                        │
│                                      │  4. Celery    │                        │
│                                      │  Worker       │                        │
│                                      │  (process_    │                        │
│                                      │   recording)  │                        │
│                                      └──────────────┘                        │
│                                               │                              │
│                              ┌────────────────┼────────────────┐             │
│                              ▼                ▼                ▼             │
│                     ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│                     │  5. Gladia   │  │  6. Speaker  │  │  7. Mistral  │    │
│                     │  Transkript- │  │  ID (Auto-   │  │  PV generie- │    │
│                     │  ion         │  │  Enrollment) │  │  ren         │    │
│                     └──────────────┘  └──────────────┘  └──────────────┘    │
│                                               │                │             │
│                                               ▼                ▼             │
│                                      ┌──────────────┐  ┌──────────────┐    │
│                                      │  8. DB:      │  │  9. DB:      │    │
│                                      │  Transkript  │  │  PV + Actions│    │
│                                      └──────────────┘  └──────────────┘    │
│                                                              │               │
│                                                              ▼               │
│                                                     ┌──────────────┐        │
│                                                     │ 10. Frontend │        │
│                                                     │  Polling     │        │
│                                                     │ (Status)     │        │
│                                                     └──────────────┘        │
│                                                              │               │
│                                                              ▼               │
│                                                     ┌──────────────┐        │
│                                                     │ 11. OnlyOffice│       │
│                                                     │  PV editieren │       │
│                                                     │ (Collaborativ)│       │
│                                                     └──────────────┘        │
│                                                              │               │
│                                                              ▼               │
│                                                     ┌──────────────┐        │
│                                                     │ 12. PV validie│       │
│                                                     │ ren + Export  │       │
│                                                     │ (PDF/DOCX)    │       │
│                                                     └──────────────┘        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Schritt-für-Schritt Analyse

### Schritt 1: Meeting erstellen

**Dateien:**
- `backend/app/api/v1/meetings.py` — API Endpoint
- `backend/app/services/meeting_service.py` — Business Logic

**Flow:**
```
Frontend POST /api/v1/meetings
  │
  ├── 1. Meeting in DB erstellen (Meeting + Participants + Agendas)
  │
  ├── 2. n8n Webhook "meeting-created" triggern
  │      URL: settings.N8N_WEBHOOK_MEETING_CREATED
  │      Payload: {id, client_id, title, attendees, ...}
  │
  ├── 3. LiveKit Room erstellen (non-blocking)
  │      LiveKitService().create_room(meeting_id)
  │
  └── 4. Audit Log (ISO 27001)
         AuditService.log_action("MEETING_CREATED")
```

**Datenbank:**
- `meetings` — Haupttabelle
- `participants` — Teilnehmer
- `agendas` — Tagesordnungspunkte

---

### Schritt 2: LiveKit Room + Audio

**Dateien:**
- `frontend/src/components/meetings/MeetingRoom.tsx` — Frontend UI
- `backend/app/api/v1/rooms.py` — Token-Generierung
- `backend/app/services/livekit_service.py` — LiveKit API

**Flow:**
```
Frontend lädt MeetingRoom
  │
  ├── 1. LiveKit Token anfordern
  │      GET /api/v1/meetings/{id}/livekit-token
  │      → {token, serverUrl}
  │
  ├── 2. LiveKitRoom Komponente verbindet
  │      <LiveKitRoom token={token} serverUrl={url}>
  │        ├── Audio-Track publizieren
  │        ├── ParticipantsList anzeigen
  │        └── RoomAudioRenderer für Sound
  │
  ├── 3. Mikrofon-Status prüfen
  │      MicToggleBridge prüft ob Track publiziert
  │      micEnabled = true NUR wenn Track sender existiert
  │
  └── 4. Recording Button enabled
         → Nur wenn: roomConnectionReady + micEnabled
```

**LiveKit Konfiguration:**
- `peerConnectionTimeout: 60000`
- `websocketTimeout: 60000`
- `maxRetries: 3`

---

### Schritt 3: Egress Recording

**Dateien:**
- `frontend/src/components/meetings/MeetingRoom.tsx` — Start/Stop Handler
- `backend/app/api/v1/recordings.py` — API Endpoints
- `backend/app/services/recording_service.py` — Upload Logic

**Flow:**
```
User klickt "Start Recording"
  │
  ├── 1. Mikrofon-Check (Track publiziert?)
  │      if (!track.sender) → enableMicrophone()
  │
  ├── 2. API Call: POST /api/v1/meetings/{id}/start-recording
  │      → {recording_id, egress_id}
  │
  ├── 3. LiveKit Egress startet
  │      → RoomCompositeEgress (alle Audio-Tracks)
  │      → WebM Format
  │      → MinIO Upload via Webhook
  │
  └── 4. Recording Status: "recording"

User klickt "Stop Recording"
  │
  ├── 1. API Call: POST /api/v1/meetings/{id}/stop-recording
  │
  ├── 2. LiveKit Egress stoppt
  │      → Egress speichert Datei in MinIO
  │      → Webhook: egress_ended
  │
  ├── 3. Recording Status: "processing"
  │
  └── 4. Celery Task gestartet
         process_recording.delay(recording_id, client_id)
```

**MinIO Struktur:**
```
meeting-recordings/
└── {meeting_id}/
    └── {uuid}_stream.webm
```

---

### Schritt 4: Celery Worker (Process Recording)

**Dateien:**
- `backend/app/tasks/transcription_tasks.py` — Hauptpipeline
- `backend/app/tasks/celery_app.py` — Celery Konfiguration

**Flow:**
```
process_recording(recording_id, client_id)
  │
  ├── 1. Recording aus DB laden
  │      Status: "uploaded" → "processing"
  │
  ├── 2. Audio aus MinIO laden
  │      S3Client.download_fileobj()
  │
  ├── 3. Gladia Transkription
  │      → Audio hochladen
  │      → Warten auf Ergebnis (Polling)
  │      → Segmente mit Speaker-Labels
  │
  ├── 4. Speaker Identification
  │      → Auto-Enrollment (ONNX 192-dim)
  │      → Phonetic Matching (Double Metaphone)
  │      → Fuzzy Matching
  │
  ├── 5. Mistral PV generieren
  │      → Dual-Context (Sentinel Summary + Display Transcript)
  │      → Temperature 0.1
  │
  ├── 6. Actions extrahieren
  │      → Assignee Resolution (6-Schritte)
  │      → Confidence Scoring
  │
  └── 7. DB aktualisieren
         ├── recording.status = "completed"
         ├── transcription segments speichern
         ├── PV + Actions speichern
         └── Audit Log
```

**Timing (verifiziert):**
| Phase | Dauer |
|-------|-------|
| Gladia Upload | ~10s |
| Gladia Polling | ~110s |
| Speaker ID | ~5s |
| Mistral PV | ~15s |
| **Gesamt** | **~140s** |

---

### Schritt 5: Frontend Polling

**Dateien:**
- `frontend/src/components/meetings/MeetingRoom.tsx` — Polling Logic

**Flow:**
```
Recording Status = "processing"
  │
  ├── Polling gestartet (alle 8s)
  │   GET /api/v1/meetings/{id}/ai-insights
  │
  ├── Response enthält:
  │   ├── status: "processing" | "completed" | "failed"
  │   ├── transcription: {segments: [...]}
  │   ├── insights: [{topic, confidence, actions}]
  │   └── pv_id: "..."
  │
  └── Wenn status = "completed":
      ├── Polling stoppen
      ├── Transcription anzeigen
      ├── Actions anzeigen
      └── PV Edit Button enabled
```

---

### Schritt 6: OnlyOffice PV Editieren

**Dateien:**
- `frontend/src/pages/OnlyOfficePage.tsx` — OnlyOffice UI
- `frontend/src/services/onlyoffice.ts` — API Client
- `backend/app/api/v1/pv.py` — Config Endpoint
- `infrastructure/kubernetes/staging/onlyoffice-deployment.yaml` — OnlyOffice Server

**Flow:**
```
User klickt "Edit PV"
  │
  ├── 1. OnlyOffice Config anfordern
  │      GET /api/v1/pv/{pv_id}/onlyoffice/config
  │      → {document: {url, key, title}, editorConfig: {...}}
  │
  ├── 2. OnlyOffice Document Server
  │      → Lädt DOCX aus MinIO
  │      → Collaborative Editing
  │      → JWT Auth
  │
  ├── 3. Speichern
  │      → OnlyOffice speichert in MinIO
  │      → Callback URL: /api/v1/pv/{pv_id}/onlyoffice/callback
  │
  └── 4. PDF/DOCX Export
         GET /api/v1/pv/{pv_id}/export?format=pdf&language=fr
```

**OnlyOffice Konfiguration:**
- Image: `onlyoffice/documentserver:9.4.0`
- JWT Secret: `production-onlyoffice-secret-jwt-key-2026`
- Storage: MinIO via S3 API
- Cache: nginx proxy_cache

---

### Schritt 7: PV Validierung + Export

**Dateien:**
- `backend/app/services/pv_service.py` — Validation Logic
- `backend/app/services/pdf_service.py` — PDF Export
- `backend/app/services/docx_service.py` — DOCX Export

**Flow:**
```
User klickt "Validate PV"
  │
  ├── 1. PV Status ändern
  │      pv.is_validated = True
  │      pv.status = "published"
  │
  ├── 2. Actions zuweisen
  │      → Assignee Resolution
  │      → Confidence Scoring
  │      → Status: "suggested" → "accepted"
  │
  ├── 3. n8n Webhook triggern
  │      POST /webhooks/n8n/pv-validated
  │      → Benachrichtigungen senden
  │
  └── 4. Audit Log
         AuditService.log_action("PV_VALIDATED")

User klickt "Export PDF"
  │
  ├── 1. PDF generieren
  │      PdfService.generate_pv_pdf(pv_id, language)
  │
  ├── 2. Template anwenden
  │      → Firmen-Logo
  │      → Header/Footer
  │      → Watermark (optional)
  │
  └── 3. Download
         → Blob → URL.createObjectURL → Download
```

---

## 3. Datenbank-Schema (relevant)

```sql
-- Meetings
CREATE TABLE meetings (
    id UUID PRIMARY KEY,
    client_id UUID NOT NULL,
    title VARCHAR(500),
    description TEXT,
    status VARCHAR(50),
    creator_id UUID,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    created_at TIMESTAMP
);

-- Recordings
CREATE TABLE recordings (
    id UUID PRIMARY KEY,
    client_id UUID NOT NULL,
    meeting_id UUID REFERENCES meetings(id),
    file_path VARCHAR(1000),
    status VARCHAR(50),  -- idle/recording/processing/completed/failed
    egress_id VARCHAR(200),
    format VARCHAR(100),
    created_at TIMESTAMP
);

-- Transcriptions
CREATE TABLE transcriptions (
    id UUID PRIMARY KEY,
    recording_id UUID REFERENCES recordings(id),
    client_id UUID NOT NULL,
    segments JSONB,  -- [{speaker, text, start, end}]
    created_at TIMESTAMP
);

-- PV (Procès-Verbal)
CREATE TABLE pv (
    id UUID PRIMARY KEY,
    meeting_id UUID REFERENCES meetings(id),
    client_id UUID NOT NULL,
    title VARCHAR(500),
    summary TEXT,
    decisions JSONB,
    actions JSONB,
    is_validated BOOLEAN DEFAULT FALSE,
    status VARCHAR(50),  -- draft/published
    created_at TIMESTAMP
);

-- Actions
CREATE TABLE actions (
    id UUID PRIMARY KEY,
    pv_id UUID REFERENCES pv(id),
    client_id UUID NOT NULL,
    title VARCHAR(500),
    description TEXT,
    priority VARCHAR(20),
    assignee VARCHAR(200),
    deadline DATE,
    status VARCHAR(50),  -- suggested/accepted/rejected
    confidence FLOAT,
    created_at TIMESTAMP
);
```

---

## 4. API Endpoints (Zusammenfassung)

| Methode | Endpoint | Zweck |
|---------|----------|-------|
| POST | `/api/v1/meetings` | Meeting erstellen |
| GET | `/api/v1/meetings/{id}` | Meeting abrufen |
| POST | `/api/v1/meetings/{id}/start-recording` | Aufnahme starten |
| POST | `/api/v1/meetings/{id}/stop-recording` | Aufnahme stoppen |
| GET | `/api/v1/meetings/{id}/transcription` | Transkription abrufen |
| GET | `/api/v1/meetings/{id}/ai-insights` | AI Insights abrufen |
| GET | `/api/v1/pv/{id}/onlyoffice/config` | OnlyOffice Config |
| POST | `/api/v1/pv/{id}/validate` | PV validieren |
| GET | `/api/v1/pv/{id}/export?format=pdf` | PDF/DOCX Export |

---

## 5. Fehlerquellen & Bekannte Probleme

| Phase | Problem | Ursache | Lösung |
|-------|---------|---------|--------|
| **LiveKit** | WebSocket Timeout | Chrome DNS-Problem | hostNetwork + ConfigMap anpassen |
| **Egress** | "websocket url timeout" | Egress kann LiveKit nicht erreichen | LIVEKIT_URL in ConfigMap |
| **Gladia** | Rate Limiting | 429 Too Many Requests | Retry mit Backoff |
| **Mistral** | Leere PV | Kein Transkript vorhanden | Warten bis Gladia fertig |
| **OnlyOffice** | "Download failed" | JWT Secret mismatch | Secrets synchronisieren |
| **Celery** | OOM Kill | 70% Memory Usage | Limit erhöhen |

---

## 6. Monitoring & Metriken

| Metrik | Quelle | Alert-Schwelle |
|--------|--------|----------------|
| `pipeline_recordings_total` | Backend | — |
| `pipeline_failures_total` | Backend | > 5% |
| `pipeline_stage_duration_seconds` | Backend | > 90s |
| `ai:mistral:calls` | Redis | — |
| `ai:mistral:errors` | Redis | > 10% |
| `storage_usage_bytes` | Backend | > 5GB |

---

## 7. CI/CD Integration

| Step | Workflow | Trigger |
|------|----------|---------|
| Code Deploy | `deploy-production.yml` | Manual |
| Velero Backup | `pre-deploy-backup` | Vor jedem Deploy |
| Smoke Test | `deploy-production.yml` | Nach Deploy |
| Monitoring | `prometheus-rules.yaml` | Automatisch |

---

## 8. Offene Fragen

| Frage | Status |
|-------|--------|
| Soll Gladia durch einen billigeren Anbieter ersetzt werden? | ⬜ Offen |
| Soll Mistral durch Qwen ersetzt werden (lokal)? | ⬜ Offen |
| Soll OnlyOffice durch einen einfacheren Editor ersetzt werden? | ⬜ Offen |
| Soll die Pipeline auf <60s optimiert werden? | ⬜ Offen |
