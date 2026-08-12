# PRO Tenant Pipeline-Analyse

**Erstellt:** 2026-08-12
**Status:** Vollständig analysiert

---

## 1. Subscription Pläne

| Eigenschaft | GRATUIT | PRO | ENTREPRISE |
|-------------|---------|-----|------------|
| **Preis** | Kostenlos | 99 TND/Monat | 399 TND/Monat |
| **Meeting-Minuten** | 15 Min/Tag | 1800 Min/Monat | 3600 Min/Monat |
| **Storage** | 1 GB | 10 GB | 50 GB |
| **API Rate Limit** | 30/min | 120/min | 600/min |
| **Recordings/Tag** | 5 | 50 | Unbegrenzt |
| **Transkriptionen/Monat** | 10 | 200 | Unbegrenzt |
| **Celery Queue** | `transcription_gratuit` | `transcription_pro` | `transcription_pro` |
| **Sentinel LLM** | ❌ Übersprungen | ✅ Voll | ✅ Voll |
| **Worker Memory** | 1 Gi | 3 Gi | 3 Gi |

---

## 2. PRO Tenant Pipeline (Detail)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PRO TENANT PIPELINE                                       │
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
│                                      │  (PRO Queue)  │                        │
│                                      └──────────────┘                        │
│                                               │                              │
│                              ┌────────────────┼────────────────┐             │
│                              ▼                ▼                ▼             │
│                     ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│                     │  5. Gladia   │  │  6. Speaker  │  │  7. Sentinel │    │
│                     │  Transkript- │  │  ID (Auto-   │  │  LLM (Qwen)  │    │
│                     │  ion         │  │  Enrollment) │  │  Summary     │    │
│                     └──────────────┘  └──────────────┘  └──────────────┘    │
│                                               │                │             │
│                                               ▼                ▼             │
│                                      ┌──────────────┐  ┌──────────────┐    │
│                                      │  8. DB:      │  │  9. Mistral  │    │
│                                      │  Transkript  │  │  PV generie- │    │
│                                      └──────────────┘  │  ren         │    │
│                                                        └──────────────┘    │
│                                                              │               │
│                                                              ▼               │
│                                                     ┌──────────────┐        │
│                                                     │ 10. DB:      │        │
│                                                     │  PV + Actions│        │
│                                                     └──────────────┘        │
│                                                              │               │
│                                                              ▼               │
│                                                     ┌──────────────┐        │
│                                                     │ 11. Frontend │        │
│                                                     │  Polling     │        │
│                                                     └──────────────┘        │
│                                                              │               │
│                                                              ▼               │
│                                                     ┌──────────────┐        │
│                                                     │ 12. OnlyOffice│       │
│                                                     │  PV editieren │       │
│                                                     └──────────────┘        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Multi-Tenant Isolation

### 3.1 Datenbank-Isolation

```sql
-- Jede Query muss client_id filtern!
SELECT * FROM meetings WHERE client_id = :current_client_id;
SELECT * FROM recordings WHERE client_id = :current_client_id;
SELECT * FROM pv WHERE client_id = :current_client_id;
SELECT * FROM actions WHERE client_id = :current_client_id;
```

### 3.2 S3/MinIO Isolation

```python
# Bucket-Name pro Tenant
def get_bucket_name(client_id: str = None) -> str:
    if client_id:
        return f"tenant-{client_id}"
    return "meeting-recordings"  # Fallback für interne Nutzung

# PRO Tenant: tenant-{uuid}
# GRATUIT Tenant: tenant-{uuid}
# Jeder Tenant hat seinen eigenen Bucket!
```

### 3.3 Celery Queue Isolation

```python
# PRO/ENTREPRISE → transcription_pro Queue (3Gi Workers)
# GRATUIT → transcription_gratuit Queue (1Gi Workers)

async def get_transcription_queue(client_id: str, db) -> str:
    plan = await db.execute(select(Client.subscription_plan).where(Client.id == client_id))
    if plan in ("PRO", "ENTREPRISE"):
        return "transcription_pro"
    return "transcription_gratuit"
```

### 3.4 Rate Limiting

```python
# PRO: 120 API calls/min, 50 recordings/day, 200 transcriptions/month
# GRATUIT: 30 API calls/min, 5 recordings/day, 10 transcriptions/month
# ENTREPRISE: 600 API calls/min, unbegrenzt

RATE_LIMITS = {
    "GRATUIT":     (30,   5,   10),
    "PRO":         (120,  50,  200),
    "ENTREPRISE":  (600, -1,   -1),
}
```

---

## 4. PRO Tenant Pipeline-Schritte

### Schritt 1: Meeting erstellen

```python
# backend/app/services/meeting_service.py
async def create_meeting(self, meeting_in: MeetingCreate, owner_id: str, client_id: str):
    # 1. Meeting in DB erstellen (mit client_id!)
    db_meeting = Meeting(
        id=str(uuid.uuid4()),
        client_id=client_id,  # MULTI-TENANT!
        title=meeting_in.title,
        ...
    )
    
    # 2. n8n Webhook triggern
    await self._trigger_n8n_meeting_created(db_meeting)
    
    # 3. LiveKit Room erstellen
    await livekit.create_room(db_meeting.id)
```

### Schritt 2: Recording starten

```python
# backend/app/api/v1/recordings.py
@router.post("/start-recording")
async def start_recording(meeting_id: str, ...):
    # 1. Rate Limit prüfen
    rate_check = check_recording_rate_limit(client_id, plan)
    if not rate_check["allowed"]:
        raise HTTPException(429, "Recording rate limit exceeded")
    
    # 2. Storage Quota prüfen
    quota_check = check_storage_quota(client_id, subscription_plan, file_size)
    if not quota_check["allowed"]:
        raise StorageQuotaExceededError(...)
    
    # 3. LiveKit Egress starten
    egress_id = await livekit.start_egress(meeting_id)
```

### Schritt 3: Celery Pipeline (PRO)

```python
# backend/app/tasks/transcription_tasks.py
@celery_app.task
def process_recording(self, recording_id: str, client_id: str):
    # 1. Client laden
    client = db.execute(select(Client).where(Client.id == client_id))
    plan = client.subscription_plan
    
    # 2. Gladia Transkription
    transcription = await gladia.transcribe(audio_file)
    
    # 3. Speaker Identification
    speakers = await identify_speakers(transcription)
    
    # 4. SENTINEL LLM (PRO/ENTREPRISE!)
    if plan in ("PRO", "ENTREPRISE"):
        # Qwen 1.5B GGUF Summary
        sentinel_summary = await sentinel.summarize(transcription)
    else:
        # GRATUIT: Kein Sentinel (schneller, kein LLM-Overhead)
        sentinel_summary = transcription[:1000]  # Nur erster Teil
    
    # 5. Mistral PV generieren
    pv = await mistral.generate_pv(
        sentinel_summary=sentinel_summary,
        full_transcript=transcription,
        participant_names=participants,
        speaker_mappings=speakers,
    )
    
    # 6. DB speichern (mit client_id!)
    recording.status = "completed"
    recording.client_id = client_id  # MULTI-TENANT!
```

### Schritt 4: PV editieren (OnlyOffice)

```python
# backend/app/api/v1/pv.py
@router.get("/{pv_id}/onlyoffice/config")
async def get_onlyoffice_config(pv_id: str, ...):
    # 1. PV aus DB laden (mit client_id!)
    pv = await db.execute(select(PV).where(PV.id == pv_id).where(PV.client_id == client_id))
    
    # 2. OnlyOffice Config generieren
    config = {
        "document": {
            "url": presigned_url,  # MinIO Presigned URL
            "key": f"pv-{pv_id}-{language}.docx",
            "title": f"PV_{meeting.title}.docx",
        },
        "editorConfig": {
            "callbackUrl": f"{BACKEND_URL}/api/v1/pv/{pv_id}/onlyoffice/callback",
            "user": {"id": user_id, "name": user_name},
            "mode": "edit",  # Collaborative Editing
        },
    }
    return config
```

---

## 5. PRO vs GRATUIT Unterschiede

| Phase | GRATUIT | PRO |
|-------|---------|-----|
| **Celery Queue** | `transcription_gratuit` | `transcription_pro` |
| **Worker Memory** | 1 Gi | 3 Gi |
| **Sentinel LLM** | ❌ Übersprungen | ✅ Qwen 1.5B |
| **PV Qualität** | Gering (kein Summary) | Hoch (Sentinel Summary) |
| **Storage** | 1 GB | 10 GB |
| **Rate Limit** | 30/min | 120/min |
| **Recordings** | 5/Tag | 50/Tag |
| **Transkriptionen** | 10/Monat | 200/Monat |

---

## 6. Test-Plan für PRO Tenant

### 6.1 E2E Test (manuell)

```bash
# 1. PRO Tenant erstellen
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "pro-test@example.com",
    "password": "Test123!",
    "full_name": "PRO Test User",
    "company_name": "PRO Test Company",
    "plan": "PRO"
  }'

# 2. Login
TOKEN=$(curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "pro-test@example.com", "password": "Test123!"}' \
  | jq -r '.access_token')

# 3. Meeting erstellen
MEETING_ID=$(curl -X POST http://localhost:8000/api/v1/meetings \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title": "PRO Test Meeting", "description": "Test für PRO Tenant"}' \
  | jq -r '.id')

# 4. Recording starten (via Frontend oder API)
curl -X POST http://localhost:8000/api/v1/meetings/$MEETING_ID/start-recording \
  -H "Authorization: Bearer $TOKEN"

# 5. Recording stoppen (nach 30s)
sleep 30
curl -X POST http://localhost:8000/api/v1/meetings/$MEETING_ID/stop-recording \
  -H "Authorization: Bearer $TOKEN"

# 6. Status prüfen (alle 8s)
for i in {1..30}; do
  STATUS=$(curl -s http://localhost:8000/api/v1/meetings/$MEETING_ID/ai-insights \
    -H "Authorization: Bearer $TOKEN" | jq -r '.status')
  echo "Attempt $i: Status = $STATUS"
  if [ "$STATUS" = "completed" ]; then
    echo "✅ Pipeline completed!"
    break
  fi
  sleep 8
done

# 7. PV abrufen
curl -s http://localhost:8000/api/v1/meetings/$MEETING_ID/ai-insights \
  -H "Authorization: Bearer $TOKEN" | jq .

# 8. OnlyOffice Config abrufen
PV_ID=$(curl -s http://localhost:8000/api/v1/meetings/$MEETING_ID/ai-insights \
  -H "Authorization: Bearer $TOKEN" | jq -r '.pv_id')
curl -s http://localhost:8000/api/v1/pv/$PV_ID/onlyoffice/config \
  -H "Authorization: Bearer $TOKEN" | jq .
```

### 6.2 Automatisierte Tests

```bash
# E2E Tests mit PRO Tenant
E2E_TEST=true pytest tests/e2e/ -v -k "pro" --tb=short

# Rate Limit Tests
E2E_TEST=true pytest tests/e2e/test_phase96_rate_limiting.py -v

# Storage Quota Tests
E2E_TEST=true pytest tests/e2e/test_storage_quota.py -v
```

---

## 7. Bekannte Probleme

| Phase | Problem | Ursache | Lösung |
|-------|---------|---------|--------|
| **Celery** | PRO Queue leer | Kein Worker subscribed | Worker mit `-Q transcription_pro` starten |
| **Sentinel** | OOM Kill | 3 Gi Memory reicht nicht | Limit auf 4 Gi erhöhen |
| **OnlyOffice** | JWT Fehler | Secret mismatch | Secrets synchronisieren |
| **Rate Limit** | 429 Fehler | Zu viele API Calls | Client über Limit informieren |

---

## 8. Monitoring für PRO Tenant

| Metrik | Quelle | Alert-Schwelle |
|--------|--------|----------------|
| `celery_queue_depth{queue="transcription_pro"}` | Prometheus | > 10 |
| `container_memory_usage_bytes{container="celery-worker-pro"}` | Prometheus | > 2.5 Gi |
| `rate:api:{client_id}` | Redis | > 120/min |
| `rate:recording:{client_id}` | Redis | > 50/Tag |
| `storage_usage_bytes{client_id}` | MinIO | > 8 GB (80% von 10 GB) |

---

## 9. CI/CD für PRO Tenant

```yaml
# .github/workflows/deploy-production.yml
pre-deploy-backup:
  steps:
    - name: Velero Pre-Deploy Backup
      run: |
        velero backup create pre-deploy-${{ github.sha }} \
          --include-namespaces=meeting-automation \
          --ttl=336h --wait
```

---

## 10. Offene Fragen

| Frage | Status |
|-------|--------|
| Soll PRO Tenant Sentinel LLM deaktivieren können? | ⬜ Offen |
| Soll PRO Tenant mehr als 50 Recordings/Tag haben? | ⬜ Offen |
| Soll PRO Tenant Priorität in der Queue haben? | ⬜ Offen |
| Soll PRO Tenant nur einen OnlyOffice Editor haben? | ⬜ Offen |
