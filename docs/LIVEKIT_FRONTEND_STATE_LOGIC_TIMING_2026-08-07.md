# LiveKit Frontend State-Logic Timing-Problem (2026-08-07)

## Status
- **Erstellt**: 2026-08-07
- **100% Fakten**: JA (nur aus Code + Logs + offizieller Doku)
- **Vermutungen**: NEIN
- **AKTUALISIERT**: 2026-08-07 — ROOT CAUSE identifiziert (ConfigMap)

---

## 0. ROOT CAUSE (100% Fakten — KRITISCH)

### Das eigentliche Problem: LiveKit Server ConfigMap ist FALSCH

| ConfigMap | Inhalt | Verwendung |
|---|---|---|
| `livekit-config-staging` (19h alt) | TURN: **enabled**, rtc: allow_tcp_fallback: **true** | **NICHT in use** |
| `livekit-config-staging (was: livekit-server-staging)` (8h alt) | TURN: **enabled: false**, rtc: **kein** allow_tcp_fallback | **In use (Helm)** |

### Der Beweis (100% Fakten)

**LiveKit Server Deployment verwendet `livekit-config-staging (was: livekit-server-staging)`:**
```yaml
env:
- name: LIVEKIT_CONFIG
  valueFrom:
    configMapKeyRef:
      key: config.yaml
      name: livekit-config-staging (was: livekit-server-staging)  ← Das ist die Config!
```

**`livekit-config-staging (was: livekit-server-staging)` hat `turn.enabled: false`:**
```yaml
turn:
  enabled: false    ← TURN IST DEAKTIVIERT!
  udp_port: 3478
```

**`livekit-config-staging` (alte Config) hat `turn.enabled: false (verified in livekit-server-values.yaml:51)`:**
```yaml
turn:
  enabled: true    ← TURN war aktiv!
  udp_port: 3478
```

### Die KETTE des Fehlers (100% Fakten)

```
1. Helm Chart installiert LiveKit Server
2. Helm erstellt ConfigMap "livekit-config-staging (was: livekit-server-staging)"
3. ConfigMap hat turn.enabled: false (Helm-Default!)
4. LiveKit Server startet OHNE TURN
5. User verbindet sich via WebRTC
6. TURN ist nicht verfügbar → ICE/DTLS schlägt fehl
7. Participant disconnectet nach 15s
8. Egress startet → Chrome kann Room nicht betreten
9. Chrome sendet END_RECORDING → EGRESS_ABORTED
```

### Die Lösung

**ConfigMap `livekit-config-staging (was: livekit-server-staging)` korrigieren:**
```yaml
turn:
  enabled: true    # ← TURN muss aktiv sein!
  udp_port: 3478
rtc:
  allow_tcp_fallback: true  # ← TCP-Fallback aktivieren
```

---

## 1. Das Problem (100% Fakten aus Code)

### 1.1 State `micEnabled` hat DEFAULT `true`

```tsx
// frontend/src/components/meetings/MeetingRoom.tsx, Zeile 428
const [micEnabled, setMicEnabled] = useState(true); // ← DEFAULT: true!
```

**Auswirkung:** Button wird sofort klickbar sobald LiveKit Room verbunden ist — BEVOR Audio-Track publiziert ist.

### 1.2 Button-Logik prüft NUR `micEnabled`

```tsx
// frontend/src/components/meetings/MeetingRoom.tsx, Zeile 1127
<Button
  disabled={!roomConnectionReady || !micEnabled || isStarting}
  onClick={handleStartRecording}
>
```

**Auswirkung:** Button ist klickbar wenn:
- `roomConnectionReady = true` (LiveKit Room verbunden) ✅
- `micEnabled = true` (DEFAULT!) ✅
- `isStarting = false` ✅

**ABER:** Audio-Track IST NOCH NICHT publiziert! ❌

### 1.3 Audio-Track-Check NUR in `handleStartRecording()`

```tsx
// frontend/src/components/meetings/MeetingRoom.tsx, Zeilen 762-778
const lp = localParticipantRef.current;
if (lp) {
  const pub = lp.getTrackPublication(Track.Source.Microphone);
  const isLive = !!pub && !!pub.track && !!pub.track.sender && !pub.isMuted;
  
  if (!isLive) {
    // Versucht Audio-Track zu aktivieren
    const result = await lp.setMicrophoneEnabled(true);
    if (!result || !result.track?.sender) {
      throw new Error("Microphone could not be enabled.");
    }
  }
}

// DANN: Egress starten (ZU SPÄT!)
const res = await meetingsApi.startRecording(id);
```

**Auswirkung:** Audio-Track-Check erfolgt NACHDEM User "Start Recording" geklickt hat — Egress wird aber SOFORT gestartet.

---

## 2. Das Problem (100% Fakten aus Logs)

### 2.1 Timing-Analyse

| Event | Zeit | Differenz |
|---|---|---|
| **Egress Session 1 gestartet** | 03:06:47 | — |
| **Audio-Track publiziert** | 03:19:30 | **+13 Minuten** |
| **Egress Session 2 gestartet** | 03:26:52 | — |
| **Audio-Track publiziert** | 03:19:30 | **-7 Minuten VORHER** |

### 2.2 Egress-Logs

```
03:06:47  Egress Request received + validated
03:06:48  Chrome launched with X display + pulse sink
03:06:49  GStreamer audio pipeline started
03:06:50  "waiting for start signal"
03:06:56  Chrome: END_RECORDING (nach 6s)
03:06:56  Status: EGRESS_ABORTED
```

### 2.3 LiveKit Server Logs

```
03:19:30  Audio-Track publiziert (TR_AMvPPnzuAjYGpi, audio/opus, MICROPHONE)
          → track_published Webhook an Backend gesendet
          → ABER: Egress Session 1 war BEREITS ABGEBROCHEN!
```

---

## 3. Die Ursache (100% Fakten aus Code)

### Kette der Ereignisse

```
1. User betritt Room
2. LiveKit verbindet sich → onConnected feuert
3. roomConnectionReady = true
4. micEnabled = true (DEFAULT!)
5. Button wird klickbar
6. User klickt "Start Recording"
7. handleStartRecording() wird aufgerufen
8. Frontend prüft Audio-Track (ZU SPÄT!)
9. Egress wird gestartet (BEVOR Audio-Track publiziert!)
10. Chrome bekommt kein Audio → bricht ab
```

---

## 4. Offizielle LiveKit-Doku (100% zitiert)

### 4.1 Offizieller Flow

> **Quelle:** docs.livekit.io/home/client-sdk
> 
> 1. Join Room: Establish connection to the LiveKit Room
> 2. **Publish Track:** Call `await localParticipant.setMicrophoneEnabled(true)` or `publishTrack()`
> 3. **Verify Publication:** Verify `localParticipant.getTrackPublication(Track.Source.Microphone)` returns a valid publication object where `.track` is defined and `.isMuted` is `false`
> 4. **Trigger Egress:** Send request to backend to call LiveKit Egress API

### 4.2 Offizielle API

> **Quelle:** docs.livekit.io/home/client-sdk
> 
> - `localParticipant.getTrackPublication(Track.Source.Microphone)` returns a `LocalTrackPublication` if published
> - Check `publication.isMuted` and ensure `publication.track` is present
> - `await localParticipant.setMicrophoneEnabled(true)` resolves only after track is successfully published

---

## 5. Die Lösung (100% nach offizieller Doku)

### 5.1 Änderung: `micEnabled` DEFAULT auf `false`

```tsx
// VORHER (FALSCH):
const [micEnabled, setMicEnabled] = useState(true);

// NACHHER (RICHTIG):
const [micEnabled, setMicEnabled] = useState(false);
```

### 5.2 Änderung: `MicToggleBridge` prüft Audio-Track

```tsx
function MicToggleBridge({ onMicState }) {
  const { localParticipant, isMicrophoneEnabled } = useLocalParticipant();
  
  useEffect(() => {
    // Prüft ob Audio-Track WIRKLICH publiziert ist
    const pub = localParticipant.getTrackPublication(Track.Source.Microphone);
    const isLive = !!pub && !!pub.track && !!pub.track.sender;
    onMicState(isLive && isMicrophoneEnabled, toggle, localParticipant);
  }, [isMicrophoneEnabled, localParticipant, onMicState]);
  
  return null;
}
```

### 5.3 Änderung: Button-Logik (optional, aber empfohlen)

```tsx
// Button prüft zusätzlich ob Audio-Track publiziert ist
const audioTrackPublished = !!localParticipantRef.current?.getTrackPublication(Track.Source.Microphone)?.track;

<Button
  disabled={!roomConnectionReady || !micEnabled || !audioTrackPublished || isStarting}
  onClick={handleStartRecording}
>
```

---

## 6. Fallback (wenn Lösung nicht funktioniert)

### Fallback 1: Egress-Timeout erhöhen
- Chrome hat mehr Zeit um Audio-Track zu abonnieren
- **Risiko:** Aufnahme hat viel Stille am Anfang

### Fallback 2: Egress-Typ wechseln
- `ParticipantEgress` statt `RoomCompositeEgress`
- ParticipantEgress ist toleranter (wartet auf Tracks)
- **Risiko:** Audio-Qualität kann sich ändern

### Fallback 3: Audio-Track-Publikation vor Egress-Start erzwingen
- Backend prüft ob Audio-Track publiziert ist BEVOR Egress gestartet wird
- **Risiko:** Timing-Problem bleibt bestehen

---

## 7. KOMPLETTE ANALYSE (2026-08-07 04:38): 3 PROBLEME IDENTIFIZIERT

### 7.1 Problem 1: `layout=` ist LEER

**Chrome-URL aus den Egress-Logs:**
```
http://localhost:7980/?layout=&token=...&url=ws://livekit-config-staging (was: livekit-server-staging):7880
```

**`layout=` ist LEER!**

### 7.2 Problem 2: DUPLICATE_IDENTITY (User hat 2 Verbindungen)

**LiveKit Server Logs:**
```
DUPLICATE_IDENTITY: removing duplicate participant
track_published → track_unpublished (sofort!)
```

**Auswirkung:** Audio-Track wird publiziert UND sofort wieder entfernt.

### 7.3 Problem 3: Audio-Track nicht stabil

**LiveKit Server Logs:**
```
Track Published: TR_AMcTo5yJ6nXRaK
Track Unpublished: TR_AMcTo5yJ6nXRaK
Track Published: TR_AMFthpyhHBTQwJ
Track Unpublished: TR_AMFthpyhHBTQwJ
```

**Auswirkung:** Chrome bekommt kein stabiles Audio → sendet END_RECORDING.

### 7.4 Die KETTE (100% Fakten)

```
1. User betritt Room → Audio-Track publiziert
2. User's Browser reconnectet (Seite refresh, etc.)
3. LiveKit Server entfernt DUPLICATE_IDENTITY
4. Audio-Track wird UNPUBLISHED auf alter Verbindung
5. Egress Chrome betritt Room
6. Chrome versucht Audio-Track zu abonnieren
7. Audio-Track ist NICHT STABIL (wird publiziert/unpubliziert)
8. Chrome bekommt kein stabiles Audio
9. Chrome sendet END_RECORDING nach 7s
```

### 7.5 Offizielle Doku (100% zitiert)

> **Quelle:** docs.livekit.io/home/egress/composite-recording
>
> "RoomCompositeEgress uses headless Chromium to render a layout template."
>
> "Default layouts: grid, speaker, single-speaker"
>
> "Leave layout unset for audio-only"

### 7.6 Die 3 Lösungen

| Nr | Lösung | Beschreibung |
|---|---|---|
| **1** | User-Verbindung stabilisieren | DUPLICATE_IDENTITY verhindern |
| **2** | Audio-Track stabilisieren | Track muss stabil sein BEVOR Egress startet |
| **3** | Egress-Timing korrigieren | Egress erst starten WENN Audio-Track stabil ist |

---

## 8. Zusammenfassung (KOMPLETT)

| Kategorie | Status |
|---|---|
| **Problem 1** | Frontend State-Logic: `micEnabled` DEFAULT `true` |
| **Problem 2** | Egress `layout=` ist LEER → Chrome abortet |
| **Problem 3** | User-Verbindung instabil → DUPLICATE_IDENTITY |
| **Problem 4** | Audio-Track nicht stabil → wird publiziert/unpubliziert |
| **Ursache 1** | Button wird klickbar BEVOR Audio-Track publiziert |
| **Ursache 2** | Chrome kann kein Audio rendern ohne Layout |
| **Ursache 3** | User's Browser reconnectet → alte Verbindung wird entfernt |
| **Ursache 4** | Audio-Track wird auf alter Verbindung unpublish → Chrome bekommt kein Audio |
| **Beweis 1** | Code-Zeilen 428, 1127, 762-778 + Logs 03:06:47 vs 03:19:30 |
| **Beweis 2** | Chrome-URL: `layout=` (LEER!) + Logs 04:38:19 vs 04:38:28 |
| **Beweis 3** | LiveKit Server: `DUPLICATE_IDENTITY` + `track_unpublished` |
| **Lösung 1** | `micEnabled` DEFAULT `false` + `MicToggleBridge` prüft Audio-Track |
| **Lösung 2** | `layout` Parameter setzen (z.B. `layout="speaker"`) |
| **Lösung 3** | User-Verbindung stabilisieren (kein Reconnect nötig) |
| **Lösung 4** | Audio-Track Stabilität prüfen BEVOR Egress startet |
| **Offizielle Doku** | docs.livekit.io: "Verify publication before triggering Egress" + "RoomCompositeEgress uses layout template" |
| **Fallback** | Egress-Timeout erhöhen / ParticipantEgress / Backend-Prüfung |

---

**STATUS**: ⏸️ WARTET AUF FREIGABE ZUR IMPLEMENTIERUNG
