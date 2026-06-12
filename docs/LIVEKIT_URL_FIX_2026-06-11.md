# LiveKit URL Fix - 2026-06-11

## Problem Statement

LiveKit-Verbindung schlug mit "Invalid URL" Fehlermeldung fehl:
- UI Error: `serverUrl: ws//804f-5-146-126-111.ngrok-free.app` (fehlender Doppelpunkt)
- Backend sendete korrekte `wss://` URL
- Frontend zerstörte die URL durch fehlerhafte Transformation

## Configuration Files Modified

| File | Change Type | Description |
|---|---|---|
| `.env.example` | Added | `LIVEKIT_NGROK_URL` variable |
| `docker-compose.yml` | Existing | `LIVEKIT_NGROK_URL` env var (Zeile 183) |
| `backend/app/core/config.py` | Existing | `LIVEKIT_NGROK_URL` field (Zeile 84) |

## Root Cause Analysis

### Mathematischer Fehler in MeetingRoom.tsx

**Original buggy code (Zeile 536):**
```typescript
setLivekitUrl(nextLivekitUrl.startsWith('ws://') ? nextLivekitUrl : `ws${nextLivekitUrl.slice(4)}`);
```

Bei Eingabe `wss://804f-5-146-126-111.ngrok-free.app`:
1. `startsWith('ws://')` → FALSE (weil "wss://" nicht "ws://" ist)
2. `slice(4)` → entfernt "wss:" → `"//804f-..."`
3. Ergebnis: `"ws" + "//804f-..."` = `"ws//804f-..."` ❌

## Changes Made

### 1. Frontend - URL-Transformation Fix
**File:** `frontend/src/components/meetings/MeetingRoom.tsx` (Zeilen 526-541)

```typescript
// Support both old and new response formats (backward compatibility)
const nextLivekitToken = tokenRes.data.participantToken || tokenRes.data.token;
const nextLivekitUrl = tokenRes.data.serverUrl || tokenRes.data.server_url;
console.info("[LiveKit] Token response", {
  serverUrl: nextLivekitUrl,
  hasToken: Boolean(nextLivekitToken),
  tokenPrefix: nextLivekitToken?.slice(0, 12),
});
setLivekitToken(nextLivekitToken);
// TEST-ONLY: Handle both ws:// and wss:// URLs (remove for production)
// Production: Backend will return correctly formatted URLs
setLivekitUrl(
  nextLivekitUrl.startsWith('ws://') || nextLivekitUrl.startsWith('wss://')
    ? nextLivekitUrl
    : `ws://${nextLivekitUrl}`
);
```

### 2. Backend - Logging for Debugging
**File:** `backend/app/api/v1/livekit.py` (Zeilen 100-110)

```python
# TEST-ONLY: Auto-detect ngrok clients and return appropriate LiveKit URL
request_host = request.headers.get("host", "")
if settings.LIVEKIT_NGROK_URL and "ngrok" in request_host:
    server_url = settings.LIVEKIT_NGROK_URL
else:
    server_url = settings.LIVEKIT_PUBLIC_URL or settings.LIVEKIT_URL
# TEST-ONLY LOGGING - REMOVE FOR PRODUCTION
logger.info(
    f"[LiveKit Token] ngrok_detection={bool(settings.LIVEKIT_NGROK_URL and 'ngrok' in request_host)} "
    f"request_host={request_host} server_url={server_url}"
)
```

### 3. Backend - Settings Configuration
**File:** `backend/app/core/config.py` (Zeile 84)

```python
LIVEKIT_NGROK_URL: str = ""  # TEST-ONLY: Remove for production
```

### 4. Docker Compose - Environment Variable
**File:** `docker-compose.yml` (Zeile 183)

```yaml
- LIVEKIT_NGROK_URL=${LIVEKIT_NGROK_URL}
```

### 5. .env.example - Documentation
**File:** `.env.example`

```env
LIVEKIT_NGROK_URL=wss://your-ngrok-url.ngrok-free.app  # TEST-ONLY: Remove for production
```

## Verification Results

### Test: Meeting testpopo (b7570718-59cc-40c0-beb4-a7a1600e97cd)

| Pipeline Stage | Status | Evidence |
|---|---|---|
| LiveKit Token Request | ✅ | `ngrok_detection=True server_url=wss://804f-...` |
| Participant Joined | ✅ | `participant_joined` webhook received |
| Egress Recording | ✅ | `egress_started` EG_qC5kQy3kN5w9 |
| Gladia Transcription | ✅ | 10 arabische Segmente |
| Mistral PV Generation | ✅ | 1 Action generiert |
| Audit Logging | ✅ | Alle Events geloggt |

## Production Cleanup Required

### Remove Before Production Deployment

1. **MeetingRoom.tsx Zeile 535-536** - Kommentare entfernen
2. **livekit.py Zeile 106-110** - Logging entfernen oder auf DEBUG Ebene reduzieren
3. **MeetingRoom.tsx Zeile 998** - ursprüngliche Error-Logik ohne serverUrl Parameter
4. **`.env`** - `LIVEKIT_NGROK_URL` entfernen
5. **docker-compose.yml Zeile 183** - `LIVEKIT_NGROK_URL` env var entfernen

## Related Documentation

- `LIVEKIT_ROUTE_PIPELINE_2026-06-07.md` - Vollständige Pipeline
- `LIVEKIT_CONNECTION_FIX_2026-06-09.md` - Vorherige Fixes
- `PIPELINE_QUICK_WINS.md` - Performance-Optimierungen