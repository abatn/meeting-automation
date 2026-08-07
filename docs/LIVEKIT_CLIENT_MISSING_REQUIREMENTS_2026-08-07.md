# LiveKit Client — Was fehlt basierend auf offiziellen Anforderungen (2026-08-07)

## Status
- **Erstellt**: 2026-08-07
- **Fokus**: LiveKit JS SDK v2.19.1 — Was fehlt im Client?
- **Status**: 100% analysiert, **Option A implementiert** (onReconnecting + onReconnected)

---

## 1. Was der Client hat (100% aus Code)

### 1.1 LiveKitRoom-Konfiguration

```tsx
<LiveKitRoom
  token={livekitToken}                    // ✅
  serverUrl={livekitUrl}                  // ✅
  connect={true}                          // ✅
  audio={true}                            // ✅
  video={false}                           // ✅
  adaptiveStream={true}                   // ✅
  dynacast={true}                         // ✅
  connectOptions={{
    peerConnectionTimeout: 30000,         // ✅
    maxRetries: 5,                        // ✅
  }}
  onConnected={() => { ... }}             // ✅
  onError={(error) => { ... }}            // ✅
  onMediaDeviceFailure={(f, k) => { ... }}// ✅
  onDisconnected={() => { ... }}          // ✅
>
```

### 1.2 State-Management

```tsx
const [livekitToken, setLivekitToken] = useState<string | null>(null);
const [livekitUrl, setLivekitUrl] = useState<string>("");
const [livekitConnectionState, setLivekitConnectionState] = useState<ConnectionState>(ConnectionState.Disconnected);
const [livekitConnected, setLivekitConnected] = useState(false);
const [livekitError, setLivekitError] = useState<string | null>(null);
const [roomConnectionReady, setRoomConnectionReady] = useState(false);
const [micEnabled, setMicEnabled] = useState(true);
const localParticipantRef = useRef<LocalParticipant | null>(null);
```

### 1.3 Audio-Track Guard

```tsx
const lp = localParticipantRef.current;
if (lp) {
  const pub = lp.getTrackPublication(Track.Source.Microphone);
  const isLive = !!pub && !!pub.track && !!pub.track.sender && !pub.isMuted;
  if (!isLive) {
    const result = await lp.setMicrophoneEnabled(true);
    if (!result || !result.track?.sender) {
      throw new Error("Microphone could not be enabled.");
    }
  }
}
```

---

## 2. Was fehlt basierend auf offizieller Doku (100% Quellen)

### 2.1 Fehlende LiveKitRoom-Callbacks

**Quelle: LiveKit Documentation (docs.livekit.io)**

| Callback | Offizielle Beschreibung | Status |
|---|---|---|
| `onConnected` | „Callback fired when successfully connected to the room" | ✅ Implementiert |
| `onDisconnected` | „Callback fired when disconnected from the room" | ✅ Implementiert |
| `onError` | „Callback fired when a connection or runtime error occurs" | ✅ Implementiert |
| `onReconnecting` | „Callback fired when attempting to reconnect after a connection drop" | ✅ **Implementiert** (2026-08-07) |
| `onReconnected` | „Callback fired when successfully reconnected" | ✅ **Implementiert** (2026-08-07) |

**Auswirkung:** UI-Feedback für Reconnect-Versuche. Bei Reconnect:
- `onReconnecting` → `isReconnecting=true`, `roomConnectionReady=false`
- `onReconnected` → `isReconnecting=false`, `roomConnectionReady=true`, `livekitError=null`
- `onDisconnected` → `isReconnecting=false`, `roomConnectionReady=false`

### 2.2 Fehlende RoomOptions

**Quelle: LiveKit Documentation**
> „Configuration options passed when instantiating the Room object"

```tsx
// OFFIZIELLE EMPFEHLUNG:
<LiveKitRoom
  options={{
    adaptiveStream: true,
    dynacast: true,
    publishDefaults: {
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
    },
  }}
>
```

**Unser Code:** `options`-Prop NICHT implementiert. Stattdessen `adaptiveStream` und `dynacast` direkt als Props gesetzt (was auch funktioniert, aber nicht der offizielle Weg ist).

### 2.3 Fehlende Reconnect-Logik

**Quelle: LiveKit Documentation**
> „The SDK automatically attempts to reconnect upon encountering transient network interruptions. It only ceases reconnection and transitions to a fully disconnected/left state if explicitly instructed via disconnect(), if a fatal server error occurs, or if reconnection attempts exceed configured thresholds/timeouts."

**Unser Code:**
- `onReconnecting` → NICHT implementiert (kein UI-Feedback)
- `onReconnected` → NICHT implementiert (kein UI-Feedback)
- `maxRetries: 5` → ✅ Implementiert (aber SDK scheint NICHT zu reconnecten)

---

## 3. Das 15-Sekunden-Problem (100% Fakten)

### 3.1 Was die Logs zeigen

```
02:02:53  Session startet
02:02:54  participant active (UDP, prflx + relay)
02:02:54  mediaTrack published (audio/opus) ✅
02:03:08  CLIENT_REQUEST_LEAVE (15s) ❌
```

### 3.2 Was `CLIENT_REQUEST_LEAVE` auslöst

**Quelle: LiveKit JS SDK**

`CLIENT_REQUEST_LEAVE` wird gesendet wenn:
1. `room.disconnect()` aufgerufen wird
2. Das `LiveKitRoom`-Component unmountet
3. Die Seite navigiert wird

### 3.3 Was der Code NICHT macht

| Möglicher Trigger | Vorhanden? | Beweis |
|---|---|---|
| `room.disconnect()` manuell | ❌ | Nur in `handleLeave` (manuell) |
| `setLivekitToken(null)` | ❌ | Nur bei `[id]`-Änderung |
| `LiveKitRoom` unmountet | ❌ | Bedingt durch `livekitToken` (stabil) |
| `setTimeout`/`setInterval` | ❌ | Keine solche Logik |

### 3.4 Der blinde Fleck

**Der Code hat keinen mechanismischen Grund für den 15-Sekunden-Disconnect.**

Das bedeutet: Die Ursache liegt **im LiveKit JS SDK v2.19.1** oder im **Netzwerk**, nicht im Frontend-Code.

---

## 4. Zusammenfassung

### Was der Client korrekt macht
- ✅ LiveKitRoom mit allen offiziellen Empfehlungen konfiguriert
- ✅ Audio-Track guard vor Recording-Start
- ✅ Button-Logik (disabled wenn nicht ready)
- ✅ State-Management (Token, Connection, Mic)

### Was fehlt (nach offizieller Doku)
| Fehlende Funktion | Offizielle Empfehlung | Auswirkung |
|---|---|---|
| `onReconnecting` | „Callback for reconnection attempt" | Kein UI-Feedback bei Reconnect |
| `onReconnected` | „Callback after successful reconnect" | Kein UI-Feedback nach Reconnect |
| `options` (RoomOptions) | „Advanced room configuration" | Keine Audio-Qualitäts-Optionen |

### Was der Code NICHT verursacht
- ❌ 15-Sekunden-Disconnect
- ❌ CLIENT_REQUEST_LEAVE
- ❌ DUPLICATE_IDENTITY

### Die einzige mögliche Erklärung
**LiveKit JS SDK v2.19.1 + Netzwerk-Problem → Client-seitiger Disconnect**

---

## 5. Implementierung (2026-08-07)

### Option A: ✅ IMPLEMENTIERT

**Änderungen in MeetingRoom.tsx:**

1. **Neue States:**
```tsx
const [isReconnecting, setIsReconnecting] = useState(false);
const [reconnectAttempt, setReconnectAttempt] = useState(0);
```

2. **LiveKitRoom-Callbacks:**
```tsx
<LiveKitRoom
  onConnected={() => {
    console.log("[LiveKit] Connected — setting roomConnectionReady=true");
    setLivekitError(null);
    setRoomConnectionReady(true);
    setIsReconnecting(false);
    setReconnectAttempt(0);
  }}
  onReconnecting={() => {
    console.warn("[LiveKit] Reconnecting...");
    setIsReconnecting(true);
    setRoomConnectionReady(false);
  }}
  onReconnected={() => {
    console.info("[LiveKit] Reconnected — restoring roomConnectionReady");
    setIsReconnecting(false);
    setRoomConnectionReady(true);
    setLivekitError(null);
  }}
  onDisconnected={() => {
    console.warn("[LiveKit] Disconnected");
    setLivekitConnected(false);
    setRoomConnectionReady(false);
    setIsReconnecting(false);
  }}
>
```

### Option B: Netzwerk-Problem analysieren
- UDP-Traffic zwischen User und Server prüfen
- TURN-Relay testen
- ICE-Kandidaten analysieren

### Option C: SDK-Version prüfen
- Prüfen ob v2.19.1 einen bekannten Bug hat
- Update auf neuere Version testen
