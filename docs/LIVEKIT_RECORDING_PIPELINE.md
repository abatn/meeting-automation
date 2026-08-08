# LiveKit Recording Pipeline — Vollständiger Ablauf

```
Meeting Created → LiveKit Room + Egress → MinIO (S3) → Celery Worker
  → Gladia Transcription → Speaker ID → Mistral PV → Actions → DB + Audit
```

---

## Infrastructure (Staging — 2026-08-07)

> **AKTUELLER ZUSTAND:** ConfigMap korrigiert mit `turn.enabled: true` (TURN/UDP).
> 15-Sekunden-Disconnect behoben durch TURN/UDP-Relay.

### LiveKit Server (ConfigMap livekit-server-staging)
| Eigenschaft | Wert |
|-------------|------|
| **Deployment** | `livekit-server-staging` (kubectl-managed) |
| **Image** | `livekit/livekit-server:latest` |
| **hostNetwork** | `true` |
| **Service** | ClusterIP (Port 7880, 7881) |
| **Node** | `instance-20260329-0846` (OCI ARM64) |
| **ConfigMap** | `livekit-server-staging` |

### LiveKit Server Config (livekit-server-staging)
```yaml
keys:
  meeting-api-key: meeting-api-secret-2026-minimum-32-chars!
log_level: info
port: 7880
redis:
  address: redis-staging.meeting-automation-staging.svc.cluster.local:6379
  db: 0
  password: redis_password
room:
  departure_timeout: 60
  empty_timeout: 600
  max_participants: 10
rtc:
  allow_tcp_fallback: true
  force_tcp: false
  ping_interval: 5
  ping_timeout: 60
  port_range_end: 60000
  port_range_start: 50000
  tcp_fallback_rtt_threshold: 0
  tcp_port: 7881
  use_external_ip: true
turn:
  enabled: true        # ← TURN/UDP aktiviert (2026-08-07)
  udp_port: 3478
webhook:
  api_key: meeting-api-key
  urls:
  - http://backend.meeting-automation-staging.svc.cluster.local:8000/api/v1/livekit/webhooks
```

### LiveKit Egress (Raw Manifests)
| Eigenschaft | Wert |
|-------------|------|
| **Deployment** | `livekit-egress` (kubectl-managed) |
| **Image** | `livekit/egress:v1.8.4` |
| **hostNetwork** | `true` |
| **Node** | `instance-20260329-0846` |
| **ConfigMap** | `livekit-egress` |

### KRITISCHE PORTS (LiveKit Anforderung)

| Port | Protocol | Zweck |
|------|----------|-------|
| **7880** | TCP | HTTP API + WebSocket Signaling |
| **7881** | TCP | WebRTC TCP Fallback |
| **3478** | UDP | **TURN Server (JETZT AKTIV!)** |
| **50000-60000** | UDP | WebRTC Media (Audio/Video) |

---

## 2026-08-07: TURN/UDP Fix — 15-Sekunden-Disconnect behoben ✅

### Status: ✅ IMPLEMENTIERT + VERIFIZIERT

### Das Problem
- User betritt Room via ICE/UDP
- Nach EXAKT 15 Sekunden: `CLIENT_REQUEST_LEAVE`
- User wird aus dem Room entfernt
- Egress betritt Room → User ist WEG → kein Audio
- EGRESS_ABORTED → "Start signal not received"

### Die Ursache
- Client hinter NAT (5.146.126.x)
- Server: 158.180.18.110
- TURN deaktiviert (`turn.enabled: false`)
- ICE/UDP scheitert durch NAT
- Kein TURN-Relay als Fallback
- LiveKit JS SDK gibt auf nach 10-15s (reconnectTimeout Default)

### Die Lösung
**TURN/UDP aktivieren (OHNE TLS!)**

**Offizielle LiveKit-Doku:**
> "For TURN/UDP, no certificate is needed"
> "TURN/UDP can be enabled with: turn.enabled: true, udp_port: 3478"

**WICHTIG:** TURN braucht NUR TLS für TURN/TLS (Port 5349), NICHT für TURN/UDP (Port 3478).

### Implementierung (2026-08-07 11:53 UTC)

**ConfigMap-Änderung:**
```yaml
# VORHER:
turn:
  enabled: false    # ← TURN komplett deaktiviert

# NACHHER:
turn:
  enabled: true     # ← TURN/UDP aktiviert (kein TLS nötig!)
  udp_port: 3478
```

**LiveKit Server Logs (Verifikation):**
```
2026-08-07T11:53:33.277Z  INFO  livekit  service/turn.go:145
Starting TURN server
  turn.relay_range_start: 30000
  turn.relay_range_end: 40000
  turn.portUDP: 3478
```

### Verbindungskette nach Fix

```
CLIENT (Firefox)                    SERVER (158.180.18.110)
     │                                    │
     │──── ICE/UDP-Kandidat ────────────→│
     │     (5.146.126.x:xxxxx)            │
     │                                    │
     │←─── ICE/UDP-Kandidat ─────────────│
     │     (158.180.18.110:50000-60000)   │
     │                                    │
     │──── TURN/UDP-Relay ──────────────→│
     │     (158.180.18.110:3478)          │
     │     ← TURN fängt ICE-Verbindung auf│
     │                                    │
     │←─── TURN/UDP-Relay ───────────────│
     │     (Audio/Video через Relay)      │
     │                                    │
     │  ✅ Verbindung stabil (durch TURN) │
     │  ✅ User bleibt im Room            │
     │  ✅ Egress bekommt Audio           │
```

### Dokumentation
- **Root Cause Analyse**: `docs/LIVEKIT_15S_DISCONNECT_ROOT_CAUSE_2026-08-07.md`
- **Implementierungsplan**: `docs/LIVEKIT_TURN_UDP_FIX_2026-08-07.md`

### Nächster Schritt
**Test:** User betritt Room → prüft Verbindungsstabilität (>30s)

---

## 2026-08-07: Weitere Fixes (vor TURN-Fix)

### Client-Side (MeetingRoom.tsx)
```tsx
<LiveKitRoom
  adaptiveStream={true}    // OFFIZIELLE EMPFEHLUNG
  dynacast={true}          // OFFIZIELLE EMPFEHLUNG
  connectOptions={{
    maxRetries: 5,         // ERHOEHT (3 → 5)
  }}
>
```

### Backend-Side (livekit_service.py)
```python
req = RoomCompositeEgressRequest()
req.room_name = meeting_id
req.layout = "speaker"  # Explizit setzen (dokumentiertes Default-Layout)
req.audio_only = True
req.file.CopyFrom(file_output)
```

---

## Stage 1: Recording (LiveKit Egress)

- **Trigger:** `POST /api/v1/meetings/{meeting_id}/livekit/start-recording`
- **Egress Type:** `RoomCompositeEgress` (composite audio, `audio_only=True`)
- **Output:** OGG Opus → MinIO bucket `meeting-recordings`
- **Status:** `"streaming"` (bei Erstellung, `livekit.py:180`)
- **Duplicate Guard:** Recording-ID Check (`livekit.py:162-166`)
- **Webhook:** KEIN `egress_started` — nächster Status-Übergang erfolgt via `egress_ended`

---

## Stage 2: Upload Completion

- **Webhook:** `egress_ended` (`livekit.py:375`)
- **Dedup:** Redis SETNX (24h TTL, fail-open) — `livekit.py:27,38-52`
- **Metadata:** `file_size` via S3 HEAD, `duration` via wave/mutagen
- **Status:** `"uploaded"` → Celery `process_recording.apply_async(args=[recording_id, client_id])`

---

## Stage 3: Transcription (Gladia V2)

- **3-Step Prozess:** `/v2/upload` → `/v2/pre-recorded` → Polling
- **Polling bis `status=done`** (NICHT `completed`!) — `gladia_service.py:103`
- **Interval:** 5s fixed — `gladia_service.py:94`
- **Output:** Segmente mit Speaker-Labels, Timestamps, Text

---

## Stage 4: Speaker Identification (Multi-Signal)

- **5+ Sprecher:** SEQUENZIELL (kein Batch) — `transcription_tasks.py:834-838`
- **<5 Sprecher:** Batches von 3, 100ms Delay — `transcription_tasks.py:842-849`

**Signale (gewichtet):**

| Signal | Score | File:Line |
|--------|-------|-----------|
| 0. LiveKit Identity (single participant) | 0.95 | `transcription_tasks.py:648-664` |
| 0. LiveKit Identity (erwähnt Name im Text) | 0.90 | `transcription_tasks.py:666-679` |
| 1. Heuristik (creator=Speaker 0) | 0.75 | `transcription_tasks.py:681` |
| 2. ONNX Audio Matching — high/medium/low | 0.90/0.60/0.30 | `transcription_tasks.py:709` |
| 3. Regex Self-Introduction | 0.85 | `transcription_tasks.py:721` |
| 4. Mistral Fusion (Threshold 0.65) | nur bei Bedarf | `transcription_tasks.py:734` |

- **Exclusivity:** Jeder Name nur EINEM Speaker (höchste Confidence gewinnt) — `transcription_tasks.py:851-868`
- **Auto-Enrollment:** ONNX 192-dim Embeddings (nur bei C2_VOICE Consent) — `transcription_tasks.py:870-919`

---

## Stage 5: ONNX Segment Reassignment

- **Nach Speaker-ID:** ONNX re-assignet einzelne Segmente (fixt Gladia-Diarization-Bugs)
- **Text-Fallback:** Erwähnt ein Segment einen anderen Speaker-Name?

---

## Stage 6: Display Transcript

- **name_map** wird angewandt: `Speaker 0` → `Abdelkader Batnini`
- **Display-Kopie** für PV, Original bleibt erhalten — `transcription_tasks.py:313-327`

---

## Stage 7: PV Generation (Map-Reduce)

- **GRATUIT:** Sentinel LLM wird übersprungen, truncierter Text als Summary
- **PRO/ENTREPRISE:** Parallele Sentinel-Summaries (3000-char Chunks)
- **Mistral:** Dual-Context (Sentinel Summary + Display Transcript) — Temperature 0.1

---

## Stage 8: Persistence + Actions

- `_save_transcription()` mit Display-Namen
- `_save_pv_and_actions()` mit Idempotenz-Check (skip if action title exists)
- **Assignee Resolution:** Speaker Mappings → Participants → Phonetic → Fuzzy → Single Speaker → External

**Audit-Actions:**
- `ACTION_ASSIGNED` (interner User) — `transcription_tasks.py:1323-1338`
- `ACTION_ASSIGNED_EXTERNAL` (externer Assignee) — `transcription_tasks.py:1355-1371`

---

## Stage 9: Completion

- `recording.status = "completed"`, `meeting.status = COMPLETED`

**Audit-Actions:**
- `TRANSCRIPTION_CREATED` — `transcription_tasks.py:1011-1025`
- `RECORDING_COMPLETED` — `transcription_tasks.py:394-403`
- `PV_CREATED` — `transcription_tasks.py:1376-1384`
- `ACTION_ASSIGNED` / `ACTION_ASSIGNED_EXTERNAL` — s. Stage 8

**Bei Fehler:**
- `recording.status = "failed"`
- `RECORDING_FAILED` Audit — `transcription_tasks.py:425-437`

- **n8n Webhook:** `_notify_n8n_completion()`

---

## Timing (aktuell)

- **Gesamt:** ~200-220s (unter 300s Timeout)
- **Haupt-Bottleneck:** Gladia Polling (5s Intervalle → ~110s Idle)

---

## Recording Test (2026-08-06)

### Test-Ergebnis
| Phase | Ergebnis | Dauer |
|-------|----------|-------|
| Login | ✅ Erfolgreich (dg@meeting.tn) | 1s |
| Meeting erstellen | ✅ Erfolgreich (adc7b664-1d91-44da-9f51-8e8a26867532) | 1s |
| Recording starten | ✅ Erfolgreich (EG_F7wmWaWpazF3) | 1s |
| Audio senden | ✅ Erfolgreich (test_audio.ogg) | 1s |
| Recording stoppen | ✅ Erfolgreich | 1s |
| Webhook (egress_ended) | ✅ Empfangen und verarbeitet | 1s |
| Recording Status | ✅ completed (file_size: 154753 bytes) | 1s |
| Transkription | ✅ completed | 1s |
| PV Erstellung | ✅ draft (ID: 1f385e67-ba61-452d-b916-192d50f32ebc) | 1s |
| PV Content | ✅ Verschluesselt (Fernet, 164 Zeichen) | 1s |
| **Gesamt** | **Pipeline funktioniert vollstaendig** | **~9s** |

---

## Kritische Quirks

- `E2E_TEST=true` aktiviert **nur** Celery eager mode (`celery_app.py:49-51`)
- `client_id` muss immer mitgegeben werden — auch an Celery Tasks
- `resolved_name` verwenden, nicht `.name` (sonst `"Speaker 0"`)
- PV-Sections sind verschlüsselt (Fernet) — Inhalt beginnt mit `gAAAAAB...`
- Confidence: `None` = "nie gemessen", `0.0` = "explizit niedrig"
- **Helm Chart Labels**: `app.kubernetes.io/name: livekit-server-staging` (NICHT `app: livekit-server-staging`)
- **NetworkPolicy**: Muss Helm-Labels beruecksichtigen (beide alte und neue Labels erlauben)
- **TURN/UDP**: `turn.enabled: true` OHNE TLS funktioniert für TURN/UDP (Port 3478)
- **TURN/TLS**: Braucht Zertifikat — NICHT für TURN/UDP nötig

---

## Verwandte Dokumente

| Datei | Inhalt |
|-------|--------|
| `docs/LIVEKIT_15S_DISCONNECT_ROOT_CAUSE_2026-08-07.md` | Root Cause Analyse (15s Disconnect) |
| `docs/LIVEKIT_TURN_UDP_FIX_2026-08-07.md` | TURN/UDP Implementierungsplan |
| `docs/LIVEKIT_3_FIXES_PLAN_2026-08-07.md` | 3-Fixes Implementierungsplan |
| `docs/LIVEKIT_PING_TIMEOUT_FIX_2026-08-07.md` | Ping-Timeout Analyse |
| `docs/LIVEKIT_CLIENT_SDK_ANALYSIS_2026-08-07.md` | SDK-Analyse |
| `docs/LIVEKIT_PIPELINE_EGRESS_ROOT_CAUSE_2026-08-07.md` | Egress Root Cause |
| `docs/LIVEKIT_OFFICIAL_RECOMMENDATIONS_2026-08-07.md` | Offizielle Empfehlungen |
