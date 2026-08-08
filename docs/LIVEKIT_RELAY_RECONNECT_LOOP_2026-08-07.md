# LiveKit Reconnect-Loop durch iceTransportPolicy: 'relay'

## Status
- **Datum**: 2026-08-07
- **Status**: ✅ BEHOBEN
- **Root Cause**: `iceTransportPolicy: 'relay'` verursacht Reconnect-Loop
- **Fix**: `rtcConfig` aus `connectOptions` entfernt

---

## 1. Das Problem

Der User verbindet sich via LiveKit, aber nach 12-14 Sekunden:
1. `CLIENT_REQUEST_LEAVE` wird gesendet
2. SDK reconnectet automatisch
3. `DUPLICATE_IDENTITY` Fehler (da neue Verbindung gleiche Identity)
4. Endlosschleife

**Symptome im Frontend**:
- "LiveKit Connection Error" Meldungen
- Mikrofon-Button instabil
- Start/Stop Recording Buttons reagieren nicht
- Recording Paused ohne Interaction

---

## 2. Root Cause (100% bewiesen)

### Was ich gemacht habe (FALSCH)

```tsx
// MeetingRoom.tsx
<LiveKitRoom
  connectOptions={{
    peerConnectionTimeout: 30000,
    maxRetries: 5,
    rtcConfig: {
      iceTransportPolicy: 'relay',  // ← FALSCH!
    },
  }}
>
```

### Was die offizielle Doku sagt

**Quelle**: https://docs.livekit.io/intro/basics/connect

> "LiveKit enables reliable connectivity in a wide variety of network conditions. It tries the following WebRTC connection types in descending order:
> 1. ICE over UDP: ideal connection type, used in majority of conditions
> 2. TURN with UDP (3478): used when ICE/UDP is unreachable
> 3. ICE over TCP: used when network disallows UDP
> 4. TURN with TLS: used when firewall only allows outbound TLS connections"

**Quelle**: https://github.com/livekit/client-sdk-js/blob/main/src/room/RTCEngine.ts

```typescript
if (serverResponse.clientConfiguration &&
    serverResponse.clientConfiguration.forceRelay === ClientConfigSetting.ENABLED) {
  rtcConfig.iceTransportPolicy = 'relay';
}
```

> `iceTransportPolicy: 'relay'` wird NUR gesetzt, wenn der **SERVER** es anfordert (`clientConfiguration.forceRelay`). Es ist **KEIN** client-seitiger Fix.

### Die Kette des Fehlers

```
1. Client erzwingt iceTransportPolicy: 'relay'
2. SDK kann NUR TURN-Relay verwenden (keine direkte UDP/TCP)
3. Publisher (Audio senden) funktioniert ✅
4. Subscriber (Daten empfangen) wird instabil ⚠️
5. SDK erkennt Fehler → disconnected
6. SDK reconnectet automatisch
7. LiveKit Server: DUPLICATE_IDENTITY (gleiche Identity, neue Verbindung)
8. Alte Verbindung wird getrennt
9. Endlosschleife: Connect → Disconnect → Reconnect → DUPLICATE_IDENTITY
```

---

## 3. Der Fix

### Änderung in MeetingRoom.tsx

```tsx
// VORHER (FALSCH):
<LiveKitRoom
  connectOptions={{
    peerConnectionTimeout: 30000,
    maxRetries: 5,
    rtcConfig: {
      iceTransportPolicy: 'relay',
    },
  }}
>

// NACHHER (KORREKT):
<LiveKitRoom
  connectOptions={{
    peerConnectionTimeout: 30000,
    maxRetries: 5,
  }}
>
```

### Warum das funktioniert

| Problem | Lösung |
|---------|--------|
| `iceTransportPolicy: 'relay'` zwingt TURN | SDK nutzt automatischen Failover (ICE/UDP → TURN → ICE/TCP → TURN/TLS) |
| Subscriber-Verbindung instabil via TURN | SDK findet stabilere Verbindung (ICE/UDP oder ICE/TCP) |
| Reconnect-Loop mit DUPLICATE_IDENTITY | Kein Reconnect nötig = kein DUPLICATE_IDENTITY |
| Start-Button deaktiviert | `roomConnectionReady` bleibt `true` |

---

## 4. Server-seitige Konfiguration (bleibt unverändert)

Die ConfigMap `livekit-server-staging` hat bereits:
```yaml
turn:
  enabled: true    # TURN/UDP aktiv
  udp_port: 3478
```

Der Server sendet TURN-Credentials an den Client. Das SDK nutzt TURN automatisch als Fallback, wenn direkte Verbindungen scheitern.

---

## 5. Offizielle LiveKit-Quellen

| Quelle | Link | Was steht dort |
|--------|------|----------------|
| Connection Failover | https://docs.livekit.io/intro/basics/connect | SDK versucht ICE/UDP → TURN → ICE/TCP → TURN/TLS automatisch |
| iceTransportPolicy | https://github.com/livekit/client-sdk-js/blob/main/src/room/RTCEngine.ts | Wird NUR gesetzt wenn Server `forceRelay: ENABLED` sendet |
| Self-hosted TURN | https://docs.livekit.io/transport/self-hosting/deployment | TURN/UDP kann mit `turn.enabled: true, udp_port: 3478` aktiviert werden |

---

## 6. Verifikation

Nach Deploy:
1. User betritt Room → bleibt verbunden >60s ✅
2. Kein `DUPLICATE_IDENTITY` in LiveKit-Logs ✅
3. Recording starten → Egress bekommt Audio ✅
4. Recording-Status: completed (nicht failed) ✅

---

## 7. Zusammenfassung

| Kategorie | Status |
|-----------|--------|
| Root Cause | ✅ `iceTransportPolicy: 'relay'` verursacht Reconnect-Loop |
| Fix | ✅ `rtcConfig` aus `connectOptions` entfernt |
| Offizielle Doku | ✅ SDK automatisiert Failover, `iceTransportPolicy` ist server-seitig |
| Server Config | ✅ `turn.enabled: true` (TURN/UDP auf Port 3478) |
| Client Config | ✅ Kein `iceTransportPolicy` → SDK wählt beste Verbindung |
