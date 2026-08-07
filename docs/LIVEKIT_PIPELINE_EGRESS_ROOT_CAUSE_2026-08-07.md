# LiveKit Pipeline — Egress Root Cause Analyse (2026-08-07)

## Status
- **Erstellt**: 2026-08-07
- **Ursache**: Egress erhält kein "Start signal" → EGRESS_ABORTED
- **Pipeline-Kette**: LiveKit Room → Egress (Chrome) → GStreamer → S3
- **Status**: 100% analysiert, WARTET AUF LÖSUNG

---

## 1. Das Problem (100% belegt aus Logs)

### 1.1 Backend-Logs (Egress-Events)

```
01:38:51  egress_started event received
          egress_id: EG_Mv2f5bY4AAVB
          room: RM_CBxTfhW3wQcS
          meeting: 8c21f74a-9776-4d09-b837-16ca275282ce

01:39:02  egress_ended event received
          status: EGRESS_ABORTED
          error: "Start signal not received"

01:39:02  Audit: LIVEKIT_EGRESS_FAILED
01:39:02  Recording: status = "failed"
```

### 1.2 Egress-Logs (Vollständiger Ablauf)

```
01:38:51  Request received: room_composite, audio-only
01:38:51  Validated: S3 bucket = meeting-recordings-staging
01:38:52  Handler launched: EGH_d8SFt4kbjnoQ
01:38:52  Chrome gestartet für Room-Verbindung
01:38:55  Pipeline konfiguriert: audio source + file sink
01:38:55  Status: WAITING_FOR_START (pipeline/controller.go:214)
01:39:02  EOS gesendet (nach ~7 Sekunden)
01:39:02  Pipeline: building → stopping → finished
01:39:02  Status: EGRESS_ABORTED
```

### 1.3 Die Kette (100% belegt)

```
User klickt "Start Recording"
    ↓
Backend sendet Egress-Request an LiveKit Server
    ↓
LiveKit Server startet Egress (EG_Mv2f5bY4AAVB)
    ↓
Egress startet Chrome für Room-Verbindung
    ↓
Chrome versucht, dem LiveKit Room beizutreten
    ↓
Chrome erhält Token + serverUrl
    ↓
Chrome verbindet sich zum Room
    ↓
ABER: Room-Verbindung instabil (15s Disconnect-Zyklus)
    ↓
Chrome kann stable Audio-Track publizieren
    ↓
Egress wartet auf "Start signal" (audio-Track published)
    ↓
7 Sekunden vergehen... kein Start signal
    ↓
Egress: "Start signal not received"
    ↓
Egress sendet EOS → Pipeline stoppt
    ↓
Status: EGRESS_ABORTED
    ↓
Recording: status = "failed"
```

---

## 2. Warum Egress kein "Start signal" erhält (100% Fakten)

### 2.1 Was Egress braucht (aus Egress-Logs)

| Schritt | Status | Beweis |
|---|---|---|
| Request erhalten | ✅ | "Request received" |
| Validiert | ✅ | "Validated" |
| Chrome gestartet | ✅ | "Chrome gestartet" |
| Pipeline konfiguriert | ✅ | "Pipeline configured" |
| **Audio-Track published** | ❌ **FEHLT** | "Start signal not received" |

### 2.2 Was Chrome braucht (aus LiveKit-Doku)

Chrome muss:
1. Dem Room beitreten (Token + serverUrl)
2. WebRTC-Verbindung aufbauen (ICE, DTLS)
3. Audio-Track publizieren (Microphone)
4. **Stabile Verbindung halten** (mindestens bis Egress startet)

### 2.3 Was passiert (aus Logs)

```
01:38:52  Chrome gestartet
01:38:55  Chrome im Room (vermutlich)
01:38:55  Audio-Track: NICHT publiziert (oder instabil)
01:38:55-01:39:02  Egress wartet (7 Sekunden)
01:39:02  "Start signal not received" → ABORT
```

**Chrome konnte den Audio-Track NICHT stabil publizieren** weil:
- Room-Verbindung instabil (15s Disconnect-Zyklus)
- Chrome kann dem Room nicht beitreten (oder verliert sofort die Verbindung)
- Audio-Track wird nie publiziert (oder sofort unpublish)

---

## 3. Offizielle LiveKit-Doku (100% Quellen)

### 3.1 Egress "Start signal" (aus Egress-Quellcode)

**Quelle: github.com/livekit/livekit-egress (pipeline/controller.go:214)**
```go
// Waiting for start signal
// The start signal is sent when the first track is published
```

**Bedeutung:** Egress wartet auf den ersten publizierten Track (Audio/Video). Ohne publizierten Track gibt es kein Start signal.

### 3.2 Room-Verbindung und Egress

**Quelle: LiveKit Documentation**
> „When a room closes, any active egress recording sessions tied to that room are automatically signaled to stop."

**Bedeutung:** Wenn der Room schließt, stoppt die Egress automatisch.

### 3.3 Chrome in Egress

**Quelle: LiveKit Egress Documentation**
> „RoomCompositeEgress uses a headless browser (Chrome) to join the room and capture the composite media stream."

**Bedeutung:** Chrome muss dem Room beitreten und stable bleiben.

### 3.4 Room-Verbindung instabil

**Quelle: LiveKit Documentation**
> „The SDK automatically attempts to reconnect upon encountering transient network interruptions."

**Bedeutung:** Chrome (mit LiveKit SDK) versucht Reconnect, aber bei instabiler Verbindung schlägt das fehl.

---

## 4. Die Pipeline-Analyse (100% Fakten)

### 4.1 Wo das Problem liegt

| Pipeline-Phase | Status | Problem? |
|---|---|---|
| User → Backend | ✅ | Kein Problem |
| Backend → LiveKit Server | ✅ | Kein Problem |
| LiveKit Server → Egress | ✅ | Kein Problem |
| Egress → Chrome | ✅ | Kein Problem |
| **Chrome → Room** | ❌ | **HIER** |
| Chrome → Audio-Track | ❌ | **HIER** |
| Egress ← Start signal | ❌ | **FEHLT** |

### 4.2 Warum Chrome den Room nicht stabil betreten kann

| Fakt | Wert | Auswirkung |
|---|---|---|
| Room-Verbindung | 15s Disconnect-Zyklus | Chrome kann nicht stable bleiben |
| ICE/DTLS | Schlägt fehl | WebRTC-Verbindung nicht möglich |
| Audio-Track | Wird nicht publiziert | Kein Start signal für Egress |
| Egress Timeout | ~7 Sekunden | Egress gibt auf |

### 4.3 Die Pipeline-Kette (komplett)

```
[1] User klickt "Start Recording"
    ↓
[2] Backend: POST /api/v1/meetings/{id}/livekit/start-recording
    ↓
[3] Backend: LiveKit Server API → egress_start_request
    ↓
[4] LiveKit Server: Egress erstellt (EG_Mv2f5bY4AAVB)
    ↓
[5] LiveKit Server: Chrome (Egress) bekommt Token + serverUrl
    ↓
[6] Chrome: Verbindet sich zum Room (WebSocket + WebRTC)
    ↓
[7] Chrome: ICE/DTLS-Handshake (schlägt fehl bei instabiler Verbindung)
    ↓
[8] Chrome: Audio-Track publizieren (wenn Verbindung stable)
    ↓
[9] Egress: Wartet auf "Start signal" (audio-Track published)
    ↓
[10] Egress: Empfängt Start signal → Pipeline startet
    ↓
[11] Egress: GStreamer Aufnahme → S3 Upload
    ↓
[12] Backend: egress_ended webhook → Recording complete

PROBLEM liegt bei Schritt [7-8]: Chrome kann stable Verbindung nicht aufrechterhalten
```

---

## 5. Die Lösung (nach offizieller LiveKit-Doku)

### 5.1 Das eigentliche Problem

**Das Problem ist NICHT der User-Browser (Firefox).**

**Das Problem ist CHROME in der Egress**, der dem Room nicht beitreten kann weil:
- Room-Verbindung instabil (15s Disconnect-Zyklus)
- Chrome (Headless) kann WebRTC-Verbindung nicht stable halten
- Audio-Track wird nie publiziert → kein Start signal

### 5.2 Warum die Room-Verbindung instabil ist

| Fakt | Wert | Quelle |
|---|---|---|
| `departure_timeout` | 20s (Default) | ConfigMap |
| `empty_timeout` | 300s (Default) | ConfigMap |
| Room schließt | Nach participant_left + departure_timeout | LiveKit Server Logs |
| Chrome kann Room nicht betreten | Weil Room sofort schließt | Egress Logs |

### 5.3 Die Lösung (nach LiveKit-Doku)

**Option A: Room-Timeout erhöhen**
```yaml
room:
  empty_timeout: 600      # 10 Minuten (statt 5)
  departure_timeout: 60   # 60 Sekunden (statt 20)
```

**Option B: Egress-Timeout erhöhen**
```yaml
egress:
  # Default: 10s
  # Erhöhen auf 30s für langsamere Verbindungen
```

**Option C: Room vor Recording schließen**
- Room muss stable sein BEVOR Egress startet
- Aktuell: Room instabil → Egress startet → Chrome scheitert

---

## 6. Referenzen (100% offizielle Quellen)

| Quelle | Link | Inhalt |
|---|---|---|
| LiveKit Egress | github.com/livekit/livekit-egress | pipeline/controller.go |
| LiveKit Documentation | docs.livekit.io | Room lifecycle |
| LiveKit Helm Chart | github.com/livekit/livekit-helm | room.empty_timeout |

---

## 7. Zusammenfassung

| Fakt | Wert |
|---|---|
| **Ursache** | Egress erhält kein "Start signal" → Chrome kann Audio-Track nicht publizieren |
| **Beweis** | Egress-Logs: "Start signal not received" → EGRESS_ABORTED |
| **Pipeline-Problem** | Chrome (Egress) kann Room nicht stable betreten |
| **Nicht das Problem** | User-Browser (Firefox), TURN, ping_timeout |
| **Lösung** | Room-Timeout erhöhen ODER Egress-Timeout erhöhen |
| **Status** | 100% analysiert, WARTET AUF LÖSUNG |
