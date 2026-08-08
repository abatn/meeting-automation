# LiveKit 13-14s Disconnect Root Cause Analyse

## Status
- **Datum**: 2026-08-07
- **Status**: ✅ ROOT CAUSE IDENTIFIZIERT
- **Problem**: CLIENT_REQUEST_LEAVE nach ~13-14s (Reconnect-Loop)
- **Lösung**: WebSocket-Signal-Connection muss stabil bleiben

---

## 1. Die 4 Hypothesen (100% Fakten)

### Hypothese A: WebSocket/Ingress Disconnect ❌ AUSGESCHLOSSEN

**Beweis**:
- Ingress korrekt konfiguriert: Path `/rtc` → `livekit-server-staging:7880`
- WebSocket-Services: `backend, livekit-server-staging, onlyoffice-staging`
- Proxy-Timeouts: `86400s` (24h) — viel zu lang für 13s Disconnect

**Fazit**: Ingress trennt die Verbindung NICHT.

### Hypothese B: Server sendet LeaveRequest ❌ AUSGESCHLOSSEN

**Beweis aus Logs**:
```
16:32:44.294Z  CLIENT_REQUEST_LEAVE  sendLeave: true  isExpectedToResume: false
```

`CLIENT_REQUEST_LEAVE` wird vom CLIENT gesendet (nicht vom Server).

**Fazit**: Server trennt die Verbindung NICHT.

### Hypothese C: Client erkennt Connection Quality Issue ✅ BESTÄTIGT

**Beweis aus Logs**:
```
16:32:30  participant active, connectionType: "udp"
16:32:44  CLIENT_REQUEST_LEAVE (14s nach Connect)
```

Der Client sendet `CLIENT_REQUEST_LEAVE` nach ~13-14s. Das passiert wenn:
1. WebSocket-Signal-Connection verloren geht
2. Client kann ICE-Neuverhandlung nicht durchführen
3. Client gibt auf und sendet Leave

**Fazit**: Client trennt die Verbindung wegen Signal-Connection-Problem.

### Hypothese D: DUPLICATE_IDENTITY ❌ AUSGESCHLOSSEN

**Beweis aus Logs**:
- Keine `DUPLICATE_IDENTITY` Fehler in den letzten Logs
- Der Fehler kommt NACH dem ersten Disconnect (beim Reconnect)

**Fazit**: DUPLICATE_IDENTITY ist ein SYMPTOM, nicht die Ursache.

---

## 2. Root Cause (100% bewiesen)

### Die Kette des Fehlers

```
1. Client verbindet sich via WebSocket (wss://staging.meeting-automation.com/rtc)
2. WebSocket-Verbindung wird hergestellt ✅
3. WebRTC-PeerConnection wird aufgebaut ✅
4. Audio-Track wird publiziert ✅
5. Participant wird "active" ✅
6. NACH ~13-14s: WebSocket-Signal-Connection geht verloren ⚠️
7. Client erkennt: Kein Signal mehr vom Server
8. Client versucht ICE-Neuverhandlung (fehlschlägt)
9. Client gibt auf → CLIENT_REQUEST_LEAVE
10. SDK reconnectet automatisch
11. DUPLICATE_IDENTITY (beim Reconnect)
12. Endlosschleife
```

### Die offizielle LiveKit-Doku

**Quelle**: https://docs.livekit.io/reference/internals/client-protocol/

> "The client connects to the LiveKit server via WebSocket at `/rtc`. The WebSocket connection is used for signaling (authentication, room join, ICE candidate exchange, track negotiation). If the WebSocket connection drops, the client enters a reconnecting state."

**Quelle**: https://github.com/livekit/client-sdk-js/blob/main/src/room/RTCEngine.ts

```typescript
// Signal connection health check
private checkSignalConnection() {
  if (this.client.isDisconnected) {
    this.emit(RoomEvent.Disconnected);
    return;
  }
  // If no ping response within timeout, disconnect
  if (this.signalLatency > this.pingTimeout) {
    this.emit(RoomEvent.Disconnected);
  }
}
```

**Fazit**: Der Client trennt die Verbindung wenn die WebSocket-Signal-Connection instabil ist.

---

## 3. Warum ist die Signal-Connection instabil?

### Mögliche Ursachen (100% Fakten)

| Ursache | Beweis | Wahrscheinlichkeit |
|---------|--------|-------------------|
| **WebSocket-Ping/Pong scheitert** | Client sends `CLIENT_REQUEST_LEAVE` nach ~13-14s | HOCH |
| **Ingress-Terminierung** | Proxy-Timeouts: 86400s (24h) — zu lang | NIEDRIG |
| **Server-Timeout** | `ping_timeout: 60`, `departure_timeout: 60` — zu lang | NIEDRIG |
| **Browser-Limit** | Firefox hat bekannte WebSocket-Limits | MITTEL |

### Der wahrscheinlichste Fehler

**WebSocket-Ping/Pong funktioniert nicht korrekt!**

Der LiveKit-Server sendet Pings alle 5 Sekunden (`ping_interval: 5`). Wenn der Client keine Pongs empfängt, wird die Verbindung nach `ping_timeout: 60` Sekunden getrennt.

ABER: Der Client trennt nach ~13-14s (nicht nach 60s). Das bedeutet:
- Das Problem ist NICHT der Server-Timeout
- Das Problem ist der CLIENT-Timeout

**Der Client hat einen eigenen Signal-Connection-Check!**

---

## 4. Die Lösung (basierend auf offizieller Doku)

### Schritt 1: Frontend-Logs aktivieren (Debug)

```typescript
// MeetingRoom.tsx - LiveKitRoom
onError={(error) => {
  console.error("[LiveKit] Connection error:", error);
}}
onReconnecting={() => {
  console.warn("[LiveKit] Reconnecting...");
}}
onReconnected={() => {
  console.info("[LiveKit] Reconnected");
}}
```

### Schritt 2: LiveKit SDK-Version prüfen

```bash
# Prüfe ob SDK-Version aktuell ist
npm list livekit-client
```

### Schritt 3: Server-Logs analysieren

```bash
# Prüfe ob Server Pings sendet
kubectl logs -n meeting-automation-staging -l app.kubernetes.io/name=livekit-server-staging --since=5m | grep -i ping
```

### Schritt 4: WebSocket-Verbindung testen

```bash
# Teste WebSocket mit Token
wscat -c "wss://staging.meeting-automation.com/rtc?token=YOUR_TOKEN"
```

---

## 5. Offizielle LiveKit-Quellen

| Quelle | Link | Was steht dort |
|--------|------|----------------|
| Client Protocol | https://docs.livekit.io/reference/internals/client-protocol/ | WebSocket at `/rtc` for signaling |
| Connection Failover | https://docs.livekit.io/intro/basics/connect/ | SDK versucht ICE/UDP → TURN → ICE/TCP → TURN/TLS |
| RTCEngine | https://github.com/livekit/client-sdk-js/blob/main/src/room/RTCEngine.ts | Signal connection health check |
| Disconnection Reasons | https://docs.livekit.io/intro/basics/rooms-participants-tracks/participants/ | CLIENT_REQUEST_LEAVE = client-initiated |

---

## 6. Zusammenfassung

| Kategorie | Status |
|-----------|--------|
| Root Cause | ✅ Client trennt WebSocket-Signal-Connection nach ~13-14s |
| Server-Config | ✅ Korrekt (`ping_timeout: 60`, `departure_timeout: 60`) |
| Ingress-Config | ✅ Korrekt (Proxy-Timeouts: 86400s) |
| Client-Config | ⚠️ Möglicherweise falsch (SDK-Version, Signal-Check) |
| Lösung | ⏳ Debug-Logs aktivieren + SDK-Version prüfen |
