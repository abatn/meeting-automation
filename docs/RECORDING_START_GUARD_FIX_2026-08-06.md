# Recording Start Guard — Fall + Plan mit Fallback (2026-08-06)

## Status
- **Erstellt**: 2026-08-06
- **Ziel**: Egress-Start erst nach sicherer Audio-Publikation (offizielle LiveKit-Doku)
- **Basis**: Beweis aus echtem Frontend-Test "test helm livekit" (Meeting `88d7c7a1`)

---

## 1. Der Fall (100% belegt, keine Annahmen)

### 1.1 Symptome (echter Frontend-Test des Users)
| Beobachtung | Detail |
|---|---|
| Mikrofon nicht steuerbar | Audio-Track erst nach mehreren Reconnects publiziert |
| Stop-Button funktioniert nicht | "No active egress" — Egress existierte nicht mehr |
| Recording failed | Backend markiert Recording auf `failed` |

### 1.2 Bewiesene Timeline (Server-/Egress-/Backend-Logs)
| Zeit (UTC) | Ereignis |
|---|---|
| 23:25:28 | Egress `EG_pBnmgn4gLXzP` gestartet |
| **23:25:34** | **`END_RECORDING` → `EGRESS_ABORTED` (nur 6s später — kein Audio im Room)** |
| 23:26:05 | Participant joined (NACH dem Abort) |
| 23:27:10–23:28:24 | Mehrere connect/disconnect-Zyklen, nur `_data_track`, KEIN Audio |
| **23:28:56** | **Audio-Track publiziert** (MICROPHONE, audio/opus) — 3,5 Min nach Egress-Start |
| 23:29:10 | track_unpublished + left |

### 1.3 Code-Beweis (Frontend `MeetingRoom.tsx`)
```jsx
// Zeile ~690: LiveKitRoom connect=true, audio=true
<LiveKitRoom ... onConnected={() => setRoomConnectionReady(true)}>
  ...
</LiveKitRoom>
// Zeile ~1074: Start-Button enabled, sobald WebRTC "connected"
<Button disabled={!roomConnectionReady || isStarting} onClick={handleStartRecording}>
// Zeile 737-766: handleStartRecording → startRecording() OHNE Audio-Track-Prüfung
const res = await meetingsApi.startRecording(id);
```

**Kern-Problem:** `roomConnectionReady` = "WebRTC-Socket verbunden" — NICHT "Audio-Track publiziert".
Der Start-Button wird erlaubt, obwohl noch kein Audio im Room ist.

### 1.4 Offizieller LiveKit-Beweis (Dokumentation)
1. **LiveKit Egress Doku** (docs.livekit.io/egress):
   - *"RoomComposite egress ... stops automatically when the room ends"*
   - *"egress joins the room as a participant ... subscribes only to the tracks it needs"*
   - → Ohne publizierten Audio-Track gibt es **nichts aufzunehmen** → Egress endet (belegt: EGRESS_ABORTED nach 6s)
2. **LiveKit JS SDK Doku** (livekit-client):
   - `await room.localParticipant.setMicrophoneEnabled(true)` → **Promise resolved NACH erfolgreicher Publikation** (offizielles Muster)
   - `ParticipantEvent.TrackPublished` → Event nach erfolgreicher Publikation
   - `localParticipant.getTrackPublication(Track.Source.Microphone)` → prüft ob Audio publiziert ist
   - → Der Start darf erst nach **tatsächlicher Audio-Publikation** erfolgen

---

## 2. Plan (3 Änderungen, alle in `frontend/src/components/meetings/MeetingRoom.tsx`)

### Änderung A: MicToggleBridge — localParticipant exponieren
```tsx
function MicToggleBridge({ onMicState }: { onMicState: (enabled: boolean, toggle: () => void, participant: LocalParticipant) => void }) {
  const { localParticipant, isMicrophoneEnabled } = useLocalParticipant();
  ...
  useEffect(() => {
    onMicState(isMicrophoneEnabled, toggle, localParticipant);
  }, [isMicrophoneEnabled, toggle, localParticipant, onMicState]);
  return null;
}
```

### Änderung B: handleStartRecording — Guard vor Egress-Start
```tsx
const handleStartRecording = async () => {
  if (!id || isStarting) return;
  try {
    setIsStarting(true);
    // OFFICIAL LiveKit pattern: ensure audio track is actually published
    // livekit-client v2.19.1: KEIN TrackPublication.isPublished —
    // zuverlässiges Signal ist `pub.track.sender` (RTCRtpSender wird erst
    // gesetzt, wenn der Track im PeerConnection aktiv sendet).
    const lp = localParticipantRef.current;
    if (lp) {
      const pub = lp.getTrackPublication(Track.Source.Microphone);
      // isLive: publiziert (track + RTCRtpSender) UND nicht gemutet
      // (ein gemutetes Mikrofon würde Stille aufnehmen)
      const isLive = !!pub && !!pub.track && !!pub.track.sender && !pub.isMuted;
      if (!isLive) {
        const result = await lp.setMicrophoneEnabled(true);
        if (!result || !result.track?.sender) {
          throw new Error("Microphone could not be enabled. Check your browser permission.");
        }
      }
    }
    const res = await meetingsApi.startRecording(id);
    ...
  } catch (err) { ... }
};
```

> **API-Korrektur während Implementierung (belegt in `node_modules/livekit-client/dist/src/room/track/`)**:  
> In v2.19.1 existiert `isPublished` NICHT auf `TrackPublication`/`LocalTrackPublication`  
> (type-check Fehler: `Property 'isPublished' does not exist on type 'LocalTrackPublication'`).  
> Die korrekte, typ-sichere Prüfung ist `pub.track?.sender` (RTCRtpSender). `setMicrophoneEnabled`  
> liefert bei Erfolg eine `LocalTrackPublication` (Sonst: Browser-Berechtigung fehlt → Fehler anzeigen,  
> Egress wird NICHT gestartet).

### Änderung C: Start-Button — disabled bis Audio bereit
```tsx
<Button
  variant="contained" fullWidth disableElevation
  onClick={handleStartRecording}
  disabled={!roomConnectionReady || !micEnabled || isStarting}
  ...
>
  {!micEnabled ? "Enable microphone first" : (roomConnectionReady ? "Start recording" : "Waiting for connection")}
</Button>
```

---

## 3. Fallback

### Wenn die Implementierung fehlschlägt (Fehler-Protokoll)
1. **SOFORT STOPP** — keine weiteren Änderungen.
2. **Fehler dokumentieren** (Log, Kommando, Zeitstempel).
3. **Ursache untersuchen**: offizielle LiveKit-Doku erneut einlesen (Abschnitt 1.4),
   Frontend-Code prüfen, `npm run type-check`/`build` ausführen.
4. **Fehler beheben** (nicht umgehen).
5. Erst wenn die Hypothese nachweislich nicht 100% funktioniert → **Rollback**:
   ```bash
   cd frontend
   git checkout src/components/meetings/MeetingRoom.tsx
   npm run type-check && npm run build
   ```
   Rollback-Verifikation: Build OK, keine Änderungen am Datei-Inhalt.

### Rollback-Bewertung
| Szenario | Aktion |
|---|---|
| Type-Check-Fehler | Fix, kein Rollback (Ursache beheben) |
| Build-Fehler | Fix, kein Rollback |
| Egress startet weiterhin zu früh | Hypothese prüfen, LiveKit-Doku erneut lesen |
| Nur bei nachweislich nicht-funktionierender Hypothese | Git-Rollback der Datei |

---

## 4. Verifikation (vor User-Test)

### 4.1 Automatisch
```bash
cd frontend
npm run lint          # muss passen (CI-required)
npm run type-check    # muss passen (CI-required)
npm run build         # muss passen (CI-required)
```

### 4.2 Manuell (User, echter Frontend-Test)
1. Meeting öffnen (Creator)
2. **Warten bis Mikrofon aktiv** (Mic-Icon grün, Button zeigt "Start recording")
3. Start → Egress startet erst wenn Audio publiziert ist
4. **NICHT sofort verlassen** — mindestens 10s sprechen
5. Stop → sollte funktionieren (aktives Egress vorhanden)
6. Ergebnis: recording.status=completed, file_size >100KB, Transkription non-empty, PV non-empty

---

## 5. Referenzen
- Offizielle LiveKit Egress Doku: https://docs.livekit.io/egress/
- LiveKit JS SDK (livekit-client v2.19.1): `setMicrophoneEnabled` (Promise → `LocalTrackPublication`),
  `getTrackPublication(Track.Source.Microphone)`, Publikations-Prüfung via `pub.track?.sender`
  (kein `isPublished` in v2.19.1 — belegt in den installierten .d.ts)
- Frontend: `frontend/src/components/meetings/MeetingRoom.tsx`
- Backend: `backend/app/api/v1/livekit.py` (start-recording) — UNVERÄNDERT
- Infrastruktur: Helm-Server v1.9.0 + Helm-Egress v1.8.4 (bereits verifiziert funktionsfähig)
