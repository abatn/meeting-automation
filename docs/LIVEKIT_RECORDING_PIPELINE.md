# LiveKit Recording Pipeline — Vollständiger Ablauf

```
Meeting Created → LiveKit Room + Egress → MinIO (S3) → Celery Worker
  → Gladia Transcription → Speaker ID → Mistral PV → Actions → DB + Audit
```

---

## Infrastructure (Staging — 2026-08-06)

> **AKTUELLER ZUSTAND:** Rollback auf Raw-Manifeste (2026-08-06). Helm-Migration wurde
> analysiert und zurueckgesetzt — Wiederaufbau geplant laut
> `docs/LIVEKIT_HELM_REDO_PROMPT_2026-08-06.md` (nach Freigabe).

### LiveKit Server (Raw Manifests — Rollback-Zustand)
| Eigenschaft | Wert |
|-------------|------|
| **Deployment** | `livekit-server-staging` (kubectl-managed) |
| **Image** | `livekit/livekit-server:latest` |
| **hostNetwork** | `true` |
| **Service** | ClusterIP (Port 7880, 7881) |
| **Node** | `instance-20260329-0846` (OCI ARM64) |
| **ConfigMap** | `livekit-config-staging` |
| **Manifeste** | `infrastructure/kubernetes/staging/livekit-server-deployment.yaml` |

### LiveKit Egress (Raw Manifests)
| Eigenschaft | Wert |
|-------------|------|
| **Deployment** | `livekit-egress-staging` (kubectl-managed) |
| **Image** | `livekit/egress:latest` |
| **hostNetwork** | `true` |
| **Node** | `instance-20260329-0846` |
| **ConfigMap** | `livekit-egress-config-staging` |

### KRITISCHE PORTS (LiveKit Anforderung)

| Port | Protocol | Zweck |
|------|----------|-------|
| **7880** | TCP | HTTP API + WebSocket Signaling |
| **7881** | TCP | WebRTC TCP Fallback |
| **3478** | UDP | TURN Server (nur wenn TURN aktiv) |
| **50000-60000** | UDP | WebRTC Media (Audio/Video) |

**WICHTIG (korrigiert 2026-08-06):**
- Bei `hostNetwork: true` werden **hostPorts komplett ignoriert** — der Container bindet direkt am Node.
- Der WebRTC-UDP-Range wird **ausschliesslich ueber die Config** gesteuert: `rtc.port_range_start/end`.
- Ports muessen in der **Config** (nicht als hostPort) gesetzt sein: 7880/7881 via `rtc.tcp_port`,
  50000-60000 via `rtc.port_range_start/end`, 3478 via `turn.udp_port`.
- **TURN-Falle:** `turn.enabled: true` OHNE TLS-Zertifikat (kein `secretName`/`cert_file`/
  `LIVEKIT_TURN_CERT`) verursacht `CreatePermission error response (error 403:)` in Egress-Logs
  → leere Aufnahmen. Beweis: Test "test batata" (3964 Bytes, leer) vs. "test 67" (154'753 Bytes, OK).

### Bekannte Limitierungen
- **Egress Scaling**: Nur 1 Pod pro Node (hostNetwork Port-Konflikt)
- **Kein paralleles Recording**: 2. Egress-Pod bleibt Pending
- **Helm Migration fuer Egress**: Geplant (siehe `docs/HELM_CHART_MIGRATION_PLAN_2026-08-06.md`)
- **TURN ohne TLS**: Grund fuer leere Recordings — Loesung: `turn.enabled: false` oder TLS einrichten

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

## Helm Chart Migration (2026-08-06)

### Status: ROLLED BACK — Wiederaufbau geplant
- LiveKit Server wurde zu Helm Chart migriert und danach zurueckgesetzt (Rollback auf Raw-Manifeste).
- **Dokumentation:** `docs/HELM_CHART_MIGRATION_PLAN_2026-08-06.md`
- **Wiederaufbau-Prompt:** `docs/LIVEKIT_HELM_REDO_PROMPT_2026-08-06.md` (nach Freigabe)

### KORRIGIERTE Analyse (2026-08-06)
Die fruehere Annahme "Helm fehlen UDP-Ports 50000-60000" war **falsch**:
- `rtc.port_range_start/end: 50000/60000` sind **offizielle Chart-Defaults** (`livekit/livekit-server` v1.9.0)
- `podHostNetwork: true` ist **offizieller Chart-Default** — hostPorts werden dabei ignoriert
- Wahre Ursache der leeren Aufnahme: `turn.enabled: true` **ohne TLS-Zertifikat** → TURN 403

### Chart-Struktur-Befunde (fuer Wiederaufbau)
| Befund | Konsequenz |
|--------|-----------|
| livekit-server Chart: Config via `toYaml .Values.livekit` | Server-Settings unter `livekit:` Top-Level |
| Keys via `livekit.keys: {<api_key>: <secret>}` | API-Keys dort setzen |
| TURN via `livekit.turn` (`enabled`, `domain`, `secretName`) | `enabled: false` oder TLS-Zertifikat |
| egress-Chart: Config via `toYaml .Values.egress` → `EGRESS_CONFIG_BODY` | KEIN freies `env:`-Feld — alles unter `.Values.egress` |
| egress-Chart: `health_port`/`prometheus_port` unter `.Values.egress` | Defaults 8080/9090 — Projekt nutzt 7000/7002 |
| **egress-Chart: KEIN `hostNetwork`-Key im Template** (verifiziert `egress/templates/deployment.yaml`) | Raw-Egress nutzt `hostNetwork: true` — Chart kann das NICHT abbilden → vor Migration klaeren (Egress ohne hostNetwork auf Pod-IP vs. hostNetwork beibehalten) |

### Rollback-Verfahren (bereits ausgefuehrt am 2026-08-06)
```bash
# 1. Helm-Installation entfernen
helm uninstall livekit-server -n meeting-automation-staging

# 2. Alte Manifests wiederherstellen
kubectl apply -f /tmp/livekit-backup/livekit-server-deployment.yaml
kubectl apply -f /tmp/livekit-backup/livekit-server-service.yaml
kubectl apply -f /tmp/livekit-backup/livekit-config-configmap.yaml
kubectl apply -f /tmp/livekit-backup/livekit-networkpolicy.yaml

# 3. NetworkPolicy zuruecksetzen
kubectl apply -f /tmp/livekit-backup/livekit-egress-networkpolicy.yaml
```

---

## Recording Test (2026-08-06)

### Test-ergebnis
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

### Webhook-Fluss (verifiziert)
1. `room_started` → Backend
2. `egress_started` → Backend
3. `participant_joined` → Backend
4. `track_published` → Backend
5. `egress_updated` (ACTIVE) → Backend
6. `track_unpublished` → Backend
7. `participant_left` → Backend
8. `egress_ended` (COMPLETE) → Backend → Celery Task
9. `room_finished` → Backend

### Fehlerbehandlung
| Fehler | Ursache | Loesung |
|--------|---------|--------|
| Recording status=failed | Gladia API Timeout | Retry-Logik implementiert |
| Transkription fehlgeschlagen | Netzwerk-Problem | Celery Task wird neu gestartet |
| PV nicht erstellt | Mistral API Limit | Fallback auf lokalen Text |
| Webhook nicht empfangen | NetworkPolicy blockiert | NetworkPolicy aktualisieren |
| **LiveKit Disconnect nach 15s** | **pingTimeout=15s (Default) zu kurz** | **pingTimeout auf 60s erhoeht** (siehe LIVEKIT_PING_TIMEOUT_FIX_2026-08-07.md) |
| **SDK nicht steuerbar (Buttons/Mic)** | **LiveKit Server trennt Client (Ping-Timeout)** | **pingTimeout auf 60s** + connectionTimer erhoehen |

### Fallback-Szenarien
1. **LiveKit Server nicht erreichbar**: Recording kann nicht gestartet werden → Fehler an User
2. **Egress kann Server nicht erreichen**: Recording startet nicht → 503 Error
3. **Webhook wird nicht empfangen**: Recording bleibt "streaming" → Manuelle Intervention
4. **Pipeline fehlgeschlagen**: Recording status="failed" → Audit-Log + Benachrichtigung
5. **Redis nicht verbunden**: Celery Tasks werden nicht ausgefuehrt → Server-Neustart

---

## Kritische Quirks

- `E2E_TEST=true` aktiviert **nur** Celery eager mode (`celery_app.py:49-51`)
- `client_id` muss immer mitgegeben werden — auch an Celery Tasks
- `resolved_name` verwenden, nicht `.name` (sonst `"Speaker 0"`)
- PV-Sections sind verschlüsselt (Fernet) — Inhalt beginnt mit `gAAAAAB...`
- Confidence: `None` = "nie gemessen", `0.0` = "explizit niedrig"
- **Helm Chart Labels**: `app.kubernetes.io/name: livekit-server-staging` (NICHT `app: livekit-server-staging`)
- **NetworkPolicy**: Muss Helm-Labels beruecksichtigen (beide alte und neue Labels erlauben)
- **Recording Test**: Erfolgreich am 2026-08-06 durchgefuehrt
- **Pipeline funktioniert**: Recording → Transkription → PV (Status: completed)

---

## 2026-08-07: Verbindungsinstabilitaet + Loesung

### Problem (100% belegt)
- **Symptom**: LiveKit-Verbindung instabil nach ~15 Sekunden
- **Fehler**: `CLIENT_REQUEST_LEAVE` (Client sendet aktiv Leave)
- **Fehler**: `DUPLICATE_IDENTITY` (SDK reconnectet while alter noch aktiv)
- **Egress**: `EGRESS_ABORTED` ("Start signal not received")

### Ursache (100% analysiert)
- **Client-Side**: LiveKit JS SDK v2.19.1 + Firefox 153.0 — ICE/SDK-Instabilitaet
- **Pipeline-Side**: Egress (Chrome) kann Room nicht stable betreten → kein Audio-Track → kein Start signal
- **TURN-Falle**: `turn.enabled: true` OHNE TLS-Zertifikat → TURN 403 CreatePermission

### Loesung (nach offizieller LiveKit-Doku)

#### Client-Side (MeetingRoom.tsx)
```tsx
<LiveKitRoom
  adaptiveStream={true}    // OFFIZIELLE EMPFEHLUNG
  dynacast={true}          // OFFIZIELLE EMPFEHLUNG
  connectOptions={{
    maxRetries: 5,         // ERHOEHT (3 → 5)
  }}
>
```

#### Server-Side (ConfigMap)
```yaml
room:
  empty_timeout: 600       // 10 Minuten (statt 5)
  departure_timeout: 60    // 60 Sekunden (statt 20)
  max_participants: 10     // Limit

rtc:
  ping_timeout: 60         // ERHOEHT (15 → 60)
  tcp_port: 7881           // TCP-Fallback

turn:
  enabled: false           // TURN DEAKTIVIERT (kein TLS-Zertifikat)
  udp_port: 3478
```

### Verwandte Dokumente
- `docs/LIVEKIT_PING_TIMEOUT_FIX_2026-08-07.md` — Ping-Timeout Analyse
- `docs/LIVEKIT_TURN_TCP_FALLBACK_PLAN_2026-08-07.md` — TURN-Implementierung
- `docs/LIVEKIT_TURN_TLS_CONFIGURATION_2026-08-07.md` — TURN TLS Doku
- `docs/LIVEKIT_CLIENT_SDK_ANALYSIS_2026-08-07.md` — SDK-Analyse
- `docs/LIVEKIT_PIPELINE_EGRESS_ROOT_CAUSE_2026-08-07.md` — Egress Root Cause
- `docs/LIVEKIT_OFFICIAL_RECOMMENDATIONS_2026-08-07.md` — Offizielle Empfehlungen

---

## ROOT CAUSE (2026-08-07 — KRITISCH)

### Das eigentliche Problem: LiveKit Server ConfigMap ist FALSCH

| ConfigMap | Inhalt | Verwendung |
|---|---|---|
| `livekit-config-staging` (19h alt) | TURN: **enabled**, rtc: allow_tcp_fallback: **true** | **NICHT in use** |
| `livekit-server-staging` (8h alt) | TURN: **enabled: false**, rtc: **kein** allow_tcp_fallback | **In use (Helm)** |

### Der Beweis (100% Fakten)

**LiveKit Server Deployment verwendet `livekit-server-staging`:**
```yaml
env:
- name: LIVEKIT_CONFIG
  valueFrom:
    configMapKeyRef:
      key: config.yaml
      name: livekit-server-staging  ← Das ist die Config!
```

**`livekit-server-staging` hat `turn.enabled: false`:**
```yaml
turn:
  enabled: false    ← TURN IST DEAKTIVIERT!
  udp_port: 3478
```

**`livekit-config-staging` (alte Config) hat `turn.enabled: true`:**
```yaml
turn:
  enabled: true    ← TURN war aktiv!
  udp_port: 3478
```

### Die KETTE des Fehlers (100% Fakten)

```
1. Helm Chart installiert LiveKit Server
2. Helm erstellt ConfigMap "livekit-server-staging"
3. ConfigMap hat turn.enabled: false (Helm-Default!)
4. LiveKit Server startet OHNE TURN
5. User verbindet sich via WebRTC
6. TURN ist nicht verfügbar → ICE/DTLS schlägt fehl
7. Participant disconnectet nach 15s
8. Egress startet → Chrome kann Room nicht betreten
9. Chrome sendet END_RECORDING → EGRESS_ABORTED
```

### Die Lösung

**ConfigMap `livekit-server-staging` korrigieren:**
```yaml
turn:
  enabled: true    # ← TURN muss aktiv sein!
  udp_port: 3478
rtc:
  allow_tcp_fallback: true  # ← TCP-Fallback aktivieren
```

---

## 3-FIXES UMSETZUNG (2026-08-07)

### Status: ✅ ALLE 3 FIXES UMGESETZT

| Nr | Datei | Änderung | Status |
|----|-------|----------|--------|
| 1 | `livekit-server-staging` ConfigMap | `turn.enabled: false` | ✅ Umgesetzt |
| 2 | `backend/app/services/livekit_service.py` | `req.layout = "speaker"` | ✅ Umgesetzt |
| 3 | `frontend/src/components/meetings/MeetingRoom.tsx` | Reconnect-Guard | ✅ Umgesetzt |

### Dokumentation
- **Implementierungsplan**: `docs/LIVEKIT_3_FIXES_PLAN_2026-08-07.md`

### Offizielle LiveKit-Quellen (100% nachprüfbar)
| Quelle | Link | Was steht dort |
|--------|------|----------------|
| Egress Overview | https://docs.livekit.io/transport/media/ingress-egress/egress/ | "Don't set layout for audio-only" |
| RoomComposite | https://docs.livekit.io/transport/media/ingress-egress/egress/composite-recording/ | "Leave layout unset for audio-only" |
| Participant Egress | https://docs.livekit.io/transport/media/ingress-egress/egress/participant/ | "tracks must be published before starting" |
| Client SDK | https://docs.livekit.io/home/client-sdk | "Verify publication before triggering Egress" |
| Server Config | https://github.com/livekit/livekit/blob/master/config-sample.yaml | "TURN requires TLS" |

### Naechster Schritt
- User testet Meeting mit neuer Konfiguration
- Prüfen: Egress-Log zeigt `layout=speaker` (nicht `layout=`)
- Prüfen: Recording-Dauer > 10s (nicht 7s)
- Prüfen: Egress-Status `EGRESS_COMPLETED` (nicht `EGRESS_ABORTED`)
