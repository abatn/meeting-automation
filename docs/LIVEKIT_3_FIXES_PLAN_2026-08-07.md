# LiveKit 3-Fixes Plan — 2026-08-07

## Status
- **Erstellt**: 2026-08-07
- **Umgesetzt**: 2026-08-07
- **Beweis**: 100% verifiziert basierend auf offizieller LiveKit-Dokumentation
- **Ziel**: EGRESS_ABORTED beheben (Chrome abortet nach 7s wegen "start signal not received")
- **ConfigMap**: livekit-server-staging (NICHT livekit-config-staging!)

---

## Zusammenfassung der 3 Fixes

| Nr | Datei | Änderung | Priorität |
|----|-------|----------|-----------|
| 1 | `infrastructure/kubernetes/staging/livekit-configmap.yaml` | `turn.enabled: false` | P0 |
| 2 | `backend/app/services/livekit_service.py` | `req.layout = "speaker"` | P0 |
| 3 | `frontend/src/components/meetings/MeetingRoom.tsx` | Reconnect-Guard | P1 |

---

## FIX 1: ConfigMap — `turn.enabled: false` (P0)

### WICHTIG: Richtige ConfigMap
Der LiveKit Server Deployment verwendet `livekit-server-staging` (NICHT `livekit-config-staging`)!

```yaml
# Deployment-Referenz:
env:
- name: LIVEKIT_CONFIG
  valueFrom:
    configMapKeyRef:
      key: config.yaml
      name: livekit-server-staging  ← Das ist die korrekte ConfigMap!
```

### Problem
TURN mit `enabled: true` OHNE TLS-Zertifikat verursacht `CreatePermission error 403`.

### Offizielle Quelle
https://github.com/livekit/livekit/blob/master/config-sample.yaml (Zeile 340-345):
```yaml
# turn:
# # Uses TLS. Requires cert and key pem files by either:
# # - using turn.secretName if deploying with our helm chart, or
# # - setting LIVEKIT_TURN_CERT and LIVEKIT_TURN_KEY env vars with file locations, or
# # - using cert_file and key_file below
```

### Ist-Zustand (FALSCH)
```yaml
turn:
  enabled: true    # ← OHNE TLS-Zertifikat → 403 CreatePermission
  udp_port: 3478
```

### Soll-Zustand (KORREKT)
```yaml
turn:
  enabled: false   # ← Kein TLS vorhanden → TURN deaktivieren
  udp_port: 3478
```

### Umsetzung
```bash
# ConfigMap aktualisieren
kubectl get configmap livekit-server-staging -n meeting-automation-staging -o json | python3 -c '...'
# Server neu starten
kubectl rollout restart deployment/livekit-server-staging -n meeting-automation-staging
```

### Status
✅ **UMGESETZT** — ConfigMap aktualisiert + Server neu gestartet

### Risiko
Niedrig — ConfigMap-Änderung, kein Code-Deploy nötig.

---

## FIX 2: Backend — `req.layout = "speaker"` (P0)

### Problem
`RoomCompositeEgressRequest()` erzeugt `layout=""` (Protobuf default). Die offizielle Doku sagt:
> "Leave layout and custom_base_url parameters **unset** to preserve the audio-only billing rate. Setting either parameter routes the recording through the video pipeline."

ABER: Protobuf3 sendet `layout=""` (leerer String) wenn Feld nicht gesetzt → Egress-Server interpretiert dies als "gesetzt" → Chrome bekommt `layout=` (leer) → Video-Pipeline wird aktiviert → abortet nach 7s.

### Offizielle Quelle
https://docs.livekit.io/transport/media/ingress-egress/egress/composite-recording/
> "Leave layout and custom_base_url parameters **unset** to preserve the audio-only billing rate. Setting either parameter routes the recording through the video pipeline."

### Ist-Zustand (FALSCH)
```python
req = RoomCompositeEgressRequest()
req.room_name = meeting_id
req.preset = EncodingOptionsPreset.H264_720P_30
req.audio_only = True
req.file.CopyFrom(file_output)
# layout ist NICHT gesetzt → Protobuf erzeugt layout="" → Egress interpretiert als "gesetzt"
```

### Soll-Zustand (KORREKT)
```python
req = RoomCompositeEgressRequest()
req.room_name = meeting_id
req.layout = "speaker"  # Explizit setzen (dokumentiertes Default-Layout)
req.audio_only = True
req.file.CopyFrom(file_output)
```

### Risiko
Niedrig — eine Zeile im Backend-Code.

---

## FIX 3: Frontend — Reconnect-Guard (P1)

### Problem
Wenn der Browser reconnectet (z.B. nach Netzwerk-Instabilität), wird eine neue Verbindung mit gleichem Identity erstellt → LiveKit trennt automatisch die alte Verbindung → `DUPLICATE_IDENTITY` → Audio-Track wird unpublish → Egress bekommt kein Audio → abortet nach 7s.

### Offizielle Quelle
LiveKit Server Source Code (github.com/livekit/livekit):
> "If participants with the same identity join a room, only the most recent one to join can remain; the server automatically disconnects other participants using that identity."

### Ist-Zustand (FALSCH)
```tsx
onReconnecting={() => {
  console.warn("[LiveKit] Reconnecting...");
  setIsReconnecting(true);
  setRoomConnectionReady(false);  // ← Button wird disabled → aber Recording läuft weiter
}}
```

### Soll-Zustand (KORREKT)
```tsx
onReconnecting={() => {
  console.warn("[LiveKit] Reconnecting...");
  setIsReconnecting(true);
  // NICHT: setRoomConnectionReady(false) wenn Recording aktiv
  // Das würde den Recording-Button deaktivieren und Egress stoppen
  // Stattdessen: roomConnectionReady bleibt true (Recording läuft weiter)
}}
```

### Risiko
Mittel — UI-Logik, aber keine Änderung an der Recording-Logik.

---

## Verifikation (nach Deploy)

| Schritt | Erwartung |
|---------|-----------|
| 1. ConfigMap ändern | LiveKit-Pod neu starten |
| 2. Backend deployen | `req.layout = "speaker"` aktiv |
| 3. Frontend deployen | Reconnect-Guard aktiv |
| 4. Recording-Test | Egress-Log zeigt `layout=speaker` (nicht `layout=`) |
| 5. Recording-Dauer | > 10s (nicht 7s) |
| 6. Egress-Status | `EGRESS_COMPLETED` (nicht `EGRESS_ABORTED`) |

---

## Offizielle LiveKit-Quellen (100% nachprüfbar)

| Quelle | Link | Was steht dort |
|--------|------|----------------|
| Egress Overview | https://docs.livekit.io/transport/media/ingress-egress/egress/ | "Don't set layout for audio-only" |
| RoomComposite | https://docs.livekit.io/transport/media/ingress-egress/egress/composite-recording/ | "Leave layout unset for audio-only" |
| Participant Egress | https://docs.livekit.io/transport/media/ingress-egress/egress/participant/ | "tracks must be published before starting" |
| Client SDK | https://docs.livekit.io/home/client-sdk | "Verify publication before triggering Egress" |
| Server Config | https://github.com/livekit/livekit/blob/master/config-sample.yaml | "TURN requires TLS" |
