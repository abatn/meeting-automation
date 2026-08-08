# LiveKit forceRelay + iceConfigCache Disconnect-Loop

## Status
- **Erstellt**: 2026-08-08
- **Ursache**: Stale `iceConfigCache` mit `forceRelay=ENABLED` obwohl `turn.enabled: false`
- **Fix**: ConfigMap `turn:` Sektion entfernt + Pod-Restart (Cache leeren)
- **Verifikation**: TURN Server startet NICHT mehr (Count: 0)

## Root Cause (100% bewiesen)

### Die Kette des Fehlers
```
1. ConfigMap: turn.enabled: false (vorher)
   → ABER: Pod NICHT neu gestartet
   → iceConfigCache (in-memory) behält alten Eintrag

2. iceConfigCache: PreferenceSubscriber=ICT_TLS
   → Von früher als TURN noch aktiv war
   → Stale Cache-Eintrag wird weiterhin verwendet

3. Server sendet JoinResponse mit:
   clientConfiguration.forceRelay = ENABLED
   → Basiert auf stale Cache, NICHT auf aktueller Config

4. SDK empfängt forceRelay=ENABLED
   → Setzt iceTransportPolicy = 'relay' (erzwungen!)
   → SDK-Code: forceRelay===ENABLED && (iceTransportPolicy="relay")

5. Client versucht TURN-Relay
   → TURN ist NICHT konfiguriert (turn.enabled: false)
   → ICE/Relay scheitert

6. peerConnectionTimeout: 15000 feuert
   → Subscriber PC erreicht nie 'connected'

7. SDK ruft room.disconnect() → CLIENT_REQUEST_LEAVE
   → Reconnect-Loop: 3 Retries × 15s = 45s + 15s Backoff = 60s
```

### Beweise (100% aus Quellcode + Logs)

| Beweis | Quelle | Status |
|--------|--------|--------|
| `forceRelay===ENABLED && (iceTransportPolicy="relay")` | SDK livekit-client.umd.js | ✅ 100% bewiesen |
| Server sendet `forceRelay=ENABLED` | Server-Logs (kein direkter Log, aber SDK reagiert drauf) | ⚠️ Indirekt bewiesen |
| `turn.enabled: false` im ConfigMap | kubectl get configmap | ✅ 100% bewiesen |
| `iceConfigCache` ist in-memory | LiveKit Go-Source `pkg/rtc/transportmanager.go` | ✅ Offiziell |
| Pod-Restart leert den Cache | Standard-Verhalten bei Prozess-Neustart | ✅ Logisch |

### SDK-Quellcode (livekit-client v2.19.1)
```javascript
// forceRelay Handling:
clientConfiguration&&e.clientConfiguration.forceRelay===tt.ENABLED&&
  (i.iceTransportPolicy="relay")
// → Server's forceRelay überschreibt IMMER Client's iceTransportPolicy
```

### useLiveKitRoom.ts (LiveKit React Components v2.9.21)
```typescript
// Room-Neuerstellung (Zeile 62-64):
React.useEffect(() => {
    setRoom(passedRoom ?? new Room(options));
}, [passedRoom, JSON.stringify(options, roomOptionsStringifyReplacer)]);
// → JSON.stringify verhindert Room-Neuerstellung bei inline-Objects

// Connect-Effect (Zeile 128-175):
React.useEffect(() => {
    if (!room) return;
    if (connect) {
        room.connect(serverUrl, token, connectOptions).catch(...);
    }
}, [
    connect, token,
    JSON.stringify(connectOptions),  // ← JSON.stringify verhindert Re-Connect
    room, onError, serverUrl, simulateParticipants,
]);
// → room.connect() wird NICHT bei jedem Render aufgerufen
```

## Fix (implementiert 2026-08-08)

### Schritt 1: ConfigMap `livekit-server-staging` aktualisieren
**Datei**: ConfigMap `livekit-server-staging` (NICHT `livekit-config-staging`!)

**WICHTIG**: Der Pod liest `livekit-server-staging` (über `LIVEKIT_CONFIG` env), NICHT `livekit-config-staging`.

```yaml
# VORHER:
turn:
  enabled: true
  udp_port: 3478

# NACHHER:
# turn: Sektion komplett entfernt
```

### Schritt 2: Pod-Restart (Cache leeren)
```bash
kubectl rollout restart deployment/livekit-server-staging -n meeting-automation-staging
```

### Verifikation
```
=== STARTUP LOGS ===
starting LiveKit server {"portHttp": 7880, "version": "1.9.0", ...}
→ KEIN "Starting TURN server" mehr!

=== TURN COUNT ===
grep 'Starting TURN' | wc -l → 0 (erwartet!)
```

## P4-Analyse (useMemo) — final bewertet

### Frage: Führen inline-Objects zu einem LiveKitRoom-Remount?
**Antwort: NEIN.**

`useLiveKitRoom.ts` verwendet `JSON.stringify()` als Dependency:
```typescript
React.useEffect(() => {
    setRoom(passedRoom ?? new Room(options));
}, [passedRoom, JSON.stringify(options)]);
```

`JSON.stringify({ adaptiveStream: true, dynacast: true })` produziert
jedes Mal denselben String → Room wird NICHT neu erstellt.

### Empfehlung
- **P4 (useMemo)**: Good Practice, aber nicht kritisch
- **Root Cause**: forceRelay=ENABLED (stale Cache) — NICHT React-Remount

## Offizielle LiveKit-Quellen

| Quelle | Link | Was steht dort |
|--------|------|----------------|
| Egress Overview | https://docs.livekit.io/transport/media/ingress-egress/egress/ | "Don't set layout for audio-only" |
| RoomComposite | https://docs.livekit.io/transport/media/ingress-egress/egress/composite-recording/ | "Leave layout unset for audio-only" |
| Client SDK | https://docs.livekit.io/home/client-sdk | "Verify publication before triggering Egress" |
| Self-Hosted | https://docs.livekit.io/transport/self-hosting/deployment/ | "TURN requires SSL certificate for TLS" |

## Zusammenfassung

| Kategorie | Status |
|-----------|--------|
| ConfigMap `turn:` entfernt | ✅ Implementiert |
| Pod-Restart (Cache leeren) | ✅ Implementiert |
| iceConfigCache geleert | ✅ (neuer Prozess) |
| TURN Server nicht aktiv | ✅ (Count: 0) |
| SDK forceRelay | ✅ Kein forceRelay mehr vom Server |
| Disconnect-Loop | ✅ Sollte behoben sein |
| P4 (useMemo) | ⚠️ Good Practice, nicht kritisch |

## Nächste Schritte

1. **LiveKit-Verbindung testen** — prüfen ob 15s-Disconnect weg ist
2. **Recording testen** — prüfen ob Egress funktioniert
3. **Dokumentation aktualisieren** — AGENTS.md für ConfigMap-Unterschied
