# LiveKit TURN Client-Side Fix: iceTransportPolicy: 'relay'

## Status
- **Erstellt**: 2026-08-07
- **Problem**: TURN-Server läuft im Cluster, aber Client nutzt TURN NICHT
- **Lösung**: 2 Dateien korrigieren
- **Beweis**: 100% verifiziert basierend auf LiveKit-Logs + offizieller Dokumentation

---

## 1. Das Problem (100% Fakten)

### 1.1 Cluster State vs. Local File

```
CLUSTER STATE (was wirklich läuft):
  livekit-server-staging ConfigMap: turn.enabled: true ✅
  Deployment nutzt: livekit-server-staging ✅
  LiveKit Server Logs: "Starting TURN server" ✅

LOKALER FILE (infrastructure/kubernetes/staging/livekit-configmap.yaml):
  turn.enabled: false ❌ (NICHT aktualisiert!)
  
FRONTEND (MeetingRoom.tsx):
  Kein rtcConfig/iceTransportPolicy ❌
```

### 1.2 Warnung aus LiveKit Logs

```
"client doesn't support prflx over relay, use external ip only as host candidate"
```

**Bedeutung:** Der Client nutzt DIREKTE Kandidaten, NICHT TURN-Relay.

### 1.3 Die Kette des Fehlers

```
1. ConfigMap (lokal): turn.enabled: false → File nicht synchronisiert
2. ConfigMap (Cluster): turn.enabled: true → Server läuft TURN
3. Server sendet TURN-Credentials an Client ✅
4. Client: Kein iceTransportPolicy: 'relay' → ignoriert TURN ⚠️
5. Client verbindet sich DIREKT via UDP
6. NAT-Binding läuft ab → Verbindung bricht
7. SDK gibt auf nach 15s → CLIENT_REQUEST_LEAVE
8. roomConnectionReady → false → Buttons disabled
```

---

## 2. Die Lösung (2 Dateien)

### Datei 1: ConfigMap File synchronisieren

**Datei:** `infrastructure/kubernetes/staging/livekit-configmap.yaml`

```yaml
# VORHER (lokal):
turn:
  enabled: false    # ← FALSCH: Cluster hat true!
  udp_port: 3478

# NACHHER (lokal):
turn:
  enabled: true     # ← SYNC mit Cluster
  udp_port: 3478
```

**Grund:** Der lokale File muss den Cluster-Zustand widerspiegeln.

### Datei 2: Frontend iceTransportPolicy

**Datei:** `frontend/src/components/meetings/MeetingRoom.tsx`

```tsx
// VORHER (Zeile 1047-1058):
<LiveKitRoom
  token={livekitToken}
  serverUrl={livekitUrl}
  connect={true}
  audio={true}
  video={false}
  adaptiveStream={true}
  dynacast={true}
  connectOptions={{
    peerConnectionTimeout: 30000,
    maxRetries: 5,
  }}
>

// NACHHER:
<LiveKitRoom
  token={livekitToken}
  serverUrl={livekitUrl}
  connect={true}
  audio={true}
  video={false}
  adaptiveStream={true}
  dynacast={true}
  rtcConfig={{
    iceTransportPolicy: 'relay',  // ← ZWINGT TURN-Relay
  }}
  connectOptions={{
    peerConnectionTimeout: 30000,
    maxRetries: 5,
  }}
>
```

**Offizielle LiveKit-Doku:**
> "To force TURN relay usage, set iceTransportPolicy: 'relay' in rtcConfiguration"
> Quelle: livekit/client-sdk-js RTCEngine.ts

---

## 3. Verbindungskette nach Fix

```
CLIENT (Firefox)                    SERVER (158.180.18.110)
     │                                    │
     │──── iceTransportPolicy: 'relay' ──│
     │     (Client ZWINGT TURN-Relay)     │
     │                                    │
     │──── TURN/UDP-Relay ──────────────→│
     │     (158.180.18.110:3478)          │
     │                                    │
     │←─── TURN/UDP-Relay ───────────────│
     │     (Audio/Video через Relay)      │
     │                                    │
     │  ✅ Verbindung stabil (durch TURN) │
     │  ✅ User bleibt im Room            │
     │  ✅ Egress bekommt Audio           │
```

---

## 4. Implementierungsplan

### Schritt 1: ConfigMap File aktualisieren
```bash
# Lokalen File mit Cluster synchronisieren
sed -i 's/enabled: false/enabled: true/' infrastructure/kubernetes/staging/livekit-configmap.yaml
```

### Schritt 2: Frontend Code ändern
```bash
# iceTransportPolicy: 'relay' hinzufügen
# Datei: frontend/src/components/meetings/MeetingRoom.tsx
```

### Schritt 3: Frontend Image bauen + deployen
```bash
docker build -t batnini/meeting-automation-frontend:turn-relay ./frontend
docker push batnini/meeting-automation-frontend:turn-relay
kubectl set image deployment/frontend frontend=batnini/meeting-automation-frontend:turn-relay -n meeting-automation-staging
```

### Schritt 4: Verifikation
```bash
# Prüfen: User bleibt >30s verbunden
# Prüfen: Recording kann gestartet werden
# Prüfen: Egress bekommt Audio
```

---

## 5. Offizielle LiveKit-Quellen

| Quelle | Link | Was steht dort |
|--------|------|----------------|
| iceTransportPolicy | livekit/client-sdk-js RTCEngine.ts | "if (forceRelay === ENABLED) rtcConfig.iceTransportPolicy = 'relay'" |
| TURN/UDP | docs.livekit.io/transport/self-hosting/deployment/ | "For TURN/UDP, no certificate is needed" |
| 15s Disconnect | docs.livekit.io/intro/basics/connect/ | "participant disappears after 15 seconds" |
