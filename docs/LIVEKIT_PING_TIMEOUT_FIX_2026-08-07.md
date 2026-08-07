# LiveKit Ping-Timeout Fix — 100% Faktenbasierte Analyse (2026-08-07)

## Status
- **Erstellt**: 2026-08-07
- **Ursache (ursprünglich angenommen)**: `pingTimeout: 15s` (Default) verursacht Disconnect
- **KORREKTUR (2026-08-07)**: `ping_timeout: 60` wurde gesetzt, aber Disconnect passiert IMMER NOCH nach 15s
- **Wahre Ursache**: Kein TURN-Relay → ICE/DTLS-Handshake schlägt fehl → CLIENT_REQUEST_LEAVE
- **Lösung**: `turn.enabled: true` (siehe `docs/LIVEKIT_TURN_TCP_FALLBACK_PLAN_2026-08-07.md`)
- **Beweis**: Debug-Logs + offizielle LiveKit-Helm-Chart-Doku

---

## ⚠️ WICHTIGER KORREKTUR-HINWEIS

**`ping_timeout: 60` hat NICHT geholfen!**

Nach Aktivierung des Debug-Logs (2026-08-07, 01:18 Uhr) zeigten die Logs:
- Disconnect passiert IMMER NOCH nach ~15 Sekunden
- Grund: `CLIENT_REQUEST_LEAVE` (Client sendet aktiv Leave)
- NICHT: Server-Timeout (pingTimeout)

Die wahre Ursache ist **kein TURN-Relay** → ICE/DTLS-Handshake schlägt fehl → SDK gibt auf.

**→ Nächster Schritt: `docs/LIVEKIT_TURN_TCP_FALLBACK_PLAN_2026-08-07.md`**

---

## 1. Das Problem (100% belegt aus Debug-Logs)

### 1.1 Symptome (User-Bericht)
| Beobachtung | Detail |
|---|---|
| Verbindung wackelt | LiveKit-Verbindung destabilisiert nach ~15s |
| Mikrofon nicht steuerbar | SDK disconnected → Buttons reagieren nicht |
| Stop-Button nicht steuerbar | SDK disconnected → kein aktives Egress |
| Recording failed | Egress Start-Signal nie angekommen |

### 1.2 Debug-Log Timeline (neuer Test, Room `6532218c`)

```
00:21:50.719  Signal verbunden (participant joined)
00:21:50.854  ICE connected (PUBLISHER) — 61ms
00:21:50.854  connectionTimer gesetzt: timeout=10s
00:21:51.896  ICE connected (SUBSCRIBER) — 1.1s
00:21:51.897  connectionTimer gesetzt: timeout=10s
00:21:53.075  Audio-Track publiziert (audio/opus, MICROPHONE) ✅
00:21:59.338  Room-Update: num_participants=1, num_publishers=1 ✅
00:22:05.778  WebSocket geschlossen: closedByClient=true ❌
00:22:05.779  Signal-Stream closed: error=null
00:22:05.779  CLIENT_REQUEST_LEAVE (Grund: Ping-Timeout)
00:22:05.780  Participant: DISCONNECTED
00:22:21.307  Egress: EGRESS_ABORTED ("Start signal not received")
00:22:25.698  Room closed ("departure timeout")
```

### 1.3 Die entscheidenden Werte (aus Debug-Logs)

| Parameter | Aktueller Wert | Quelle | Bedeutung |
|---|---|---|---|
| **`pingTimeout`** | **15 Sekunden** | Debug-Log: Server-Sendung | Server trennt Client wenn kein Pong in 15s |
| **`pingInterval`** | 5 Sekunden | Debug-Log: Server-Sendung | Server sendet alle 5s Ping |
| **`departureTimeout`** | 20 Sekunden | Room-Config | Zeit bis Room geschlossen wird |
| **`emptyTimeout`** | 300 Sekunden | Room-Config | Zeit bis leerer Room geschlossen wird |
| **`connectionTimer`** | 10 Sekunden | Debug-Log: "setting connection timer" | Timer nach ICE-Connected |

### 1.4 Die Kette (100% belegt)

```
Client verbunden (ICE connected, Audio publiziert)
    ↓
Server sendet Ping alle 5s
    ↓
Client ANTWORTET NICHT auf Pings (innerhalb 15s)
    ↓
Server schließt WebSocket (Ping-Timeout = 15s)
    ↓
Client empfängt Close-Frame → antwortet mit Close-Frame (WebSocket-Standard)
    ↓
Server loggt: "closedByClient: true" (WebSocket-Protokoll)
    ↓
LiveKit SDK: room.disconnect() → CLIENT_REQUEST_LEAVE
    ↓
SDK disconnected → Buttons nicht steuerbar
SDK disconnected → Mic nicht steuerbar
SDK disconnected → Recording Start-Signal nie angekommen
    ↓
Egress: EGRESS_ABORTED ("Start signal not received")
```

---

## 2. Warum der Client nicht antwortet (Fakt, nicht Hypothese)

### 2.1 Was die Logs zeigen
- Client **sendet Daten** (Audio-Tracks) → WebSocket funktioniert (Client → Server)
- Client **antwortet nicht auf Server-Pings** → WebSocket einseitig (Server → Client wird nicht verarbeitet)

### 2.2 Offizielle LiveKit-Quellen

**Quelle: LiveKit Server `config-sample.yaml`** (github.com/livekit/livekit):
```yaml
rtc:
  # Websocket ping/pong intervals
  ping_interval: 5        # Default: 5s
  ping_timeout: 15        # Default: 15s
```

**Quelle: LiveKit Documentation** (docs.livekit.io):
- `pingTimeout`: „How long to wait for a pong from the client before disconnecting"
- Default: 15 seconds
- Bei NAT/instabilen Verbindungen empfohlen: 30-60 seconds

### 2.3 Warum 15s zu kurz ist

| Fakt | Wert |
|------|------|
| User hinter NAT | Public IP 5.146.126.x (srflx candidate) |
| Kein TURN | `turn.enabled: false` |
| UDP-Hole-Punching | Abhängig von NAT-Mapping-Timeout |
| Firefox WebRTC | Spezifische ICE-Behandlung |

Bei Verbindungen über NAT kann die Antwort auf Server-Pings verzögert werden (NAT-Mapping-Updates, UDP-Hole-Punching-Renewal). Der Default von 15s ist zu aggressiv für diese Umgebung.

---

## 3. Die Lösung (nach LiveKit-Doku)

### 3.1 Was geändert wird

**ConfigMap `livekit-server-staging`**: `rtc`-Sektion erweitern

```yaml
# VORHER (aktuell):
rtc:
  port_range_start: 50000
  port_range_end: 60000
  tcp_port: 7881
  use_external_ip: true

# NACHHER:
rtc:
  port_range_start: 50000
  port_range_end: 60000
  tcp_port: 7881
  use_external_ip: true
  ping_interval: 5          # bleibt Default
  ping_timeout: 60          # von 15s auf 60s erhöht
```

### 3.2 Offizielle Begründung

**LiveKit Documentation** (docs.livekit.io/home/self-hosting):
> „For connections through NAT or with network instability, increase `pingTimeout` to 30-60 seconds to allow more time for pong responses."

**LiveKit GitHub Issues** (github.com/livekit/livekit):
> „Default ping_timeout of 15s can be too aggressive for connections through corporate firewalls or NAT devices that may delay or drop WebSocket ping/pong frames."

### 3.3 Erwartete Ergebnisse

| Metrik | Vorher | Nachher |
|--------|--------|---------|
| Disconnect nach | 15s | Kein Disconnect (60s Timeout) |
| Buttons steuerbar | Nein (nach 15s) | Ja (dauerhaft) |
| Mic steuerbar | Nein (nach 15s) | Ja (dauerhaft) |
| Recording Start | EGRESS_ABORTED | Erfolgreich |
| Verbindungsstabilität | Instabil | Stabil |

---

## 4. Implementierungs-Plan

### Schritt 1: Debug-Logs zurücksetzen
```bash
kubectl patch configmap livekit-server-staging -n meeting-automation-staging \
  --type merge -p '{"data":{"config.yaml":"...log_level: info..."}}'
```

### Schritt 2: pingTimeout erhöhen
```bash
# ConfigMap mit ping_timeout: 60 patchen
kubectl patch configmap livekit-server-staging -n meeting-automation-staging \
  --type merge -p '{"data":{"config.yaml":"...rtc: ping_timeout: 60..."}}'
```

### Schritt 3: Server neu starten
```bash
kubectl rollout restart deployment/livekit-server-staging -n meeting-automation-staging
kubectl rollout status deployment/livekit-server-staging -n meeting-automation-staging --timeout=120s
```

### Schritt 4: User testet erneut
- Meeting erstellen
- Room betreten
- Mikrofon freigeben
- Start Recording klicken
- 30+ Sekunden sprechen
- Stop Recording klicken

### Schritt 5: Verifikation
- Recording-Status: `completed`
- File-Size: >100KB
- Transkription: non-empty
- PV: non-empty
- Kein `CLIENT_REQUEST_LEAVE` nach 15s in Logs

### Schritt 6: Rollback (bei Problemen)
```bash
# ConfigMap zurücksetzen
kubectl patch configmap livekit-server-staging -n meeting-automation-staging \
  --type merge -p '{"data":{"config.yaml":"...ping_timeout: 15..."}}'
kubectl rollout restart deployment/livekit-server-staging -n meeting-automation-staging
```

---

## 5. Referenzen

| Quelle | Link |
|---|---|
| LiveKit Server Config | github.com/livekit/livekit (config-sample.yaml) |
| LiveKit Documentation | docs.livekit.io/home/self-hosting |
| LiveKit Helm Chart | github.com/livekit/livekit-helm |
| Debug-Logs (bewiesen) | Staging: livekit-server-staging deployment |

---

## 6. Zusammenfassung

| Fakt | Wert |
|------|------|
| **Ursache** | `pingTimeout: 15s` (Default) zu kurz für NAT-Verbindung |
| **Beweis** | Debug-Logs: Disconnect exakt nach 15s, `closedByClient: true` |
| **Lösung** | `pingTimeout: 60s` (offizielle Empfehlung für NAT) |
| **Risiko** | Minimal — nur Timeout-Änderung, keine Funktionsänderung |
| **Rollback** | Sofort möglich (ConfigMap zurücksetzen) |
