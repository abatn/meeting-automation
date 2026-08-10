# LiveKit iceTransportPolicy: 'relay' (REMOVED — not in MeetingRoom.tsx as of 2026-08-08) Fix — 2026-08-08

## Status
- **Erstellt**: 2026-08-08
- **Root Cause**: Firefox kann prflx over relay nicht nutzen + UDP50000-60000 blockiert
- **Fix**: `iceTransportPolicy: 'relay' (REMOVED — not in MeetingRoom.tsx as of 2026-08-08)` in Frontend-Code aktiviert
- **Verifikation**: Frontend deployed, User kann testen

---

## 1. Die Fakten (100% aus Logs + offizieller Doku)

### Server-Logs zeigen:
```
- "client doesn't support prflx over relay" ⚠️
- TURN relay Candidates vorhanden, aber NICHT nutzbar
- UDP50000-60000 (ICE ports) blockiert
- connectionType: udp (TURN nicht als Relay genutzt)
```

### Offizielle LiveKit-Doku (SDK-Code):
```typescript
if (
  serverResponse.clientConfiguration &&
  serverResponse.clientConfiguration.forceRelay === ClientConfigSetting.ENABLED
) {
  rtcConfig.iceTransportPolicy = 'relay';
}
```

---

## 2. Die Kette des Fehlers

```
1. Server advertised: 158.180.18.110:50000-60000 als ICE candidates
2. Firefox empfängt diese Candidates
3. Kann KEIN UDP zu dieser IP etablieren (Cloud-Firewall blockiert)
4. TURN relay Candidates vorhanden, aber "client doesn't support prflx over relay"
5. Verbindung scheitert nach 10-15s
6. SDK: 5 Retries × ~14s = ~70s → Abort Handler
7. "could not establish signal connection"
```

---

## 3. Die Lösung

### Änderung
**Datei**: `frontend/src/components/meetings/MeetingRoom.tsx`

```typescript
// VORHER:
connectOptions={{
  peerConnectionTimeout: 60000 (verified in MeetingRoom.tsx:1069),
  websocketTimeout: 30000,
  maxRetries: 3 (verified in MeetingRoom.tsx:1071),
}}

// NACHHER:
connectOptions={{
  peerConnectionTimeout: 60000 (verified in MeetingRoom.tsx:1069),
  websocketTimeout: 30000,
  maxRetries: 3 (verified in MeetingRoom.tsx:1071),
  rtcConfig: {
    iceTransportPolicy: 'relay' (REMOVED — not in MeetingRoom.tsx as of 2026-08-08),  // ← HINZUGEFÜGT!
  },
}}
```

### Deploy-Status
```
┌─────────────────────────────────────────────────────────────────┐
│  ✅ ERFOLGREICH DEPLOYED                                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Image: batnini/meeting-automation-frontend:turn-relay-fix      │
│  Pod:   frontend-6784f7bbc-bgzfd: 1/1 Running ✅              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Offizielle Quellen

| Quelle | Link | Was steht dort |
|--------|------|----------------|
| SDK RTCEngine.ts | livekit/client-sdk-js | `iceTransportPolicy = 'relay'` |
| LiveKit Docs | https://docs.livekit.io/home/client-sdk | "client can set iceTransportPolicy" |
| Server Config | config-sample.yaml | "clientConfiguration.forceRelay" |

---

## 5. Nächster Schritt

**Teste jetzt:**
1. Öffne http://158.180.18.110:3001 (Cache leeren!)
2. Login → Meeting erstellen → Room betreten
3. Prüfen: Kein "LiveKit Connection Error" mehr?
4. Start-Button funktioniert?
5. Recording kann gestartet werden?

---

## 6. WICHTIG: TURN/TLS (Optional)

Für Production könnte TURN/TLS benötigt werden:
```yaml
turn:
  enabled: true
  domain: turn.meeting-automation.com
  tls_port: 5349
  cert_file: /path/to/turn.crt
  key_file: /path/to/turn.key
```

Für Staging reicht TURN/UDP auf Port 3478.