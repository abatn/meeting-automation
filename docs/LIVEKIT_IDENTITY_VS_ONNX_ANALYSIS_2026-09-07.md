# LiveKit Identity vs ONNX — Speaker Identification Analysis

**Date:** 2026-09-07
**Context:** ONNX Speaker ID is the pipeline bottleneck (260-638s on AMD64 production)
**Test Case:** test smoke 6 — ONNX took 638.50s with `intra_op_num_threads=1` (2.3x SLOWER than AUTO)

---

## Current Speaker ID Pipeline (7 signals)

| # | Signal | How it works | Score | Status |
|---|--------|-------------|-------|--------|
| 0 | **LiveKit Identity** | Single room participant → first speaker | 0.95 | ⚠️ LIMITED |
| 0b | Heuristic | Participant matching, creator detection | 0.75 | ✅ |
| 1 | **ONNX Audio** | Embedding vs enrolled profiles | 0.85 | 🔴 260-638s |
| 2 | Regex | Self-introduction detection | 0.80 | ✅ |
| 3 | Mistral Fusion | LLM-based matching | 0.70 | ✅ (10s) |
| 4 | Validation | Name must be in candidates | — | ✅ |
| 5 | Auto-enrollment | Save new speakers | — | ✅ |

---

## The Problem with LiveKit Identity (Signal 0)

```python
# Current code — LIMITED:
if len(room_participants) == 1 and speaker_index == 0:
    # Only works for SINGLE participant meetings!
    signals.append({"source": "livekit_identity", "score": 0.95})

for rp in room_participants:
    if rp_name.lower() in text_context.lower():
        # Only works if speaker MENTIONS a name in speech!
        signals.append({"source": "livekit_identity", "score": 0.90})
```

**For multi-participant meetings, LiveKit Identity is almost never used.**

---

## ⚠️ CORRECTION: LiveKit Active Speaker Detection is CLIENT-SIDE ONLY

From official LiveKit documentation (https://docs.livekit.io/intro/basics/rooms-participants-tracks/webhooks-events/):

### Available LiveKit Webhook Events (COMPLETE LIST)

```
room_started
room_finished
participant_joined
participant_left
participant_connection_aborted
track_published
track_unpublished
egress_started
egress_updated
egress_ended
ingress_started
ingress_ended
```

**There is NO `active_speaker` webhook event.**

### What LiveKit Actually Provides

| Feature | Availability | How to Access |
|---------|-------------|---------------|
| Active Speaker Detection | **Client-side ONLY** | `RoomEvent.ActiveSpeakersChanged` in JS/Swift/Kotlin SDKs |
| Speaking Status Changed | **Client-side ONLY** | `RoomEvent.ParticipantSpeakingChanged` |
| Webhook Events | **Server-side** | But NO `active_speaker` event |

### Implication for Option B

My original proposal (LiveKit active_speaker → Gladia matching) requires:

1. **Frontend changes**: Capture `RoomEvent.ActiveSpeakersChanged` events
2. **Frontend → Backend**: Send speaking timeline via WebSocket or HTTP
3. **Backend**: Store in `meeting_speaker_timeline` table
4. **Pipeline**: Match to Gladia segments

This is **~100+ lines of code** (not ~50), not a quick fix.

### What We Actually Need: "Who was speaking when?"

To implement this on the server, we would need the CLIENT to report speaking status:

```
Frontend captures:
  00:00-00:05 → Participant A (identity: 38f342a5_5aa85801)
  00:05-00:12 → Participant B (identity: 38f342a5_f9f806ce)

Frontend sends to backend via WebSocket:
  POST /api/v1/meetings/{id}/speaker-timeline
  [{"participant_id": "A", "start": 0, "end": 5}, ...]

Backend stores in DB:
  meeting_speaker_timeline table

Pipeline loads and matches to Gladia segments:
  Speaker 0 = Participant A
  Speaker 1 = Participant B
```

---

## ⚠️ Skip ONNX when 0 enrolled profiles (Quick Win)

Looking at the code:

```python
profiles_with_embeddings = [p for p in enrolled_profiles if p.embedding is not None]
if embedding is not None and profiles_with_embeddings:
    # ONNX matching — only runs if there are enrolled profiles!
```

ONNX already skips matching when 0 profiles exist. But it still runs the embedding extraction (260-638s). We could skip ONNX entirely when `len(profiles_with_embeddings) == 0`.

---

## ONNX Performance Data (Production AMD64)

| Run | ONNX Duration | Config | Status |
|-----|--------------|--------|--------|
| test smoke 2 (1st) | 304s | AUTO threads | ❌ Soft time limit |
| test smoke 4 (1st) | 265s | AUTO threads | ❌ Soft time limit |
| test smoke 5 (2nd) | 173s | AUTO threads | ✅ Completed |
| **test smoke 6 (1st)** | **638s** | **threads=1** | ❌ **2.3x SLOWER** |
| test smoke 6 (2nd) | running | threads=1 | ⏳ |

**Benchmark from docs/PIPELINE_OPTIMIZATION_STATUS_2026-08-23.md was misleading:**
- Tested 300 frames on ARM64 (27ms → 3.7ms)
- Production is AMD64 with real audio data
- `intra_op_num_threads=1` made it 2.3x SLOWER, not 11.9x faster

---

## Recommendation (CORRECTED)

| Option | Impact | Effort | Priority |
|--------|--------|--------|----------|
| **A: Skip ONNX when 0 profiles** | Saves 260-638s | ~5 lines | 🔴 P0 |
| **B: LiveKit active_speaker → Gladia matching** | Eliminates ONNX for known participants | ~100+ lines + DB + Frontend | 🟡 P1 |
| **C: Both** | Maximum improvement | ~105+ lines | 🟡 P1 |

---

## Option A: Skip ONNX when 0 profiles (Quick Win)

### Current behavior
```
0 enrolled profiles → ONNX extracts embedding → finds nothing → wastes 260-638s
```

### Proposed behavior
```
0 enrolled profiles → skip ONNX entirely → go directly to heuristic/Mistral
```

### Code change location
`backend/app/tasks/transcription_tasks.py`, line ~241:

```python
# Current:
if speaker_mappings and speaker_embedding_service.is_available:
    # ONNX segment reassignment runs even with 0 profiles

# Proposed:
if speaker_mappings and speaker_embedding_service.is_available and profiles_with_emb:
    # Only run ONNX if there are enrolled profiles to match against
```

---

## Option B: LiveKit active_speaker → Gladia matching (Long-term)

### Architecture

```
Meeting in progress:
  LiveKit Server → active_speaker events → Redis/DB (time-series)
  LiveKit Egress → room audio → MinIO

Pipeline:
  1. Load active_speaker timeline from DB
  2. Gladia diarizes audio → segments with timestamps
  3. Match Gladia segments to active_speaker timeline
  4. Speaker 0 = Participant who was active during 00:00-00:05
```

### Required changes

1. **LiveKit webhook**: Log `active_speaker_changed` events with timestamps
2. **DB schema**: `meeting_speaker_timeline` table (meeting_id, participant_id, start_time, end_time)
3. **Pipeline**: New signal between Gladia and ONNX — match via timeline overlap

### Data flow

```
LiveKit Server
  │
  ├── participant_joined → webhook → backend (room_participants)
  ├── active_speaker_changed → webhook → backend (speaker_timeline)
  │
  └── egress_ended → webhook → backend → process_recording.delay()
        │
        ├── 1. S3 download
        ├── 2. Gladia transcription + diarization
        ├── 3. Load speaker_timeline from DB
        ├── 4. Match: Gladia segments ↔ active_speaker timeline
        ├── 5. Heuristic (creator, text references)
        ├── 6. Mistral fusion (fallback)
        └── 7. Save PV + actions
```

### Advantages over ONNX

| Aspect | ONNX | LiveKit Timeline |
|--------|------|-----------------|
| Speed | 260-638s | ~0s (DB query) |
| Accuracy | 85% (embedding match) | 95%+ (actual audio source) |
| CPU usage | 1000m (full core) | ~0m |
| Dependencies | ONNX model, audio extraction | LiveKit server only |
| Known participants | Required for matching | Always available |

### Disadvantages

| Aspect | ONNX | LiveKit Timeline |
|--------|------|-----------------|
| Unknown speakers | ✅ Can enroll new speakers | ❌ Only known participants |
| Accuracy (noise) | ✅ Audio fingerprint | ⚠️ Active speaker ≠ talking |
| Implementation | ✅ Existing | 🔴 New feature required |

---

## Test smoke 6 — Full Timeline

### Recording `891d1e59`

| Time (UTC) | Event | Duration |
|-----------|-------|----------|
| 08:44:32 | process_recording received | — |
| 08:44:32 | s3_download | 0.11s |
| 08:44:46 | gladia_transcription | 13.37s |
| 08:44:48 | speaker_id_profile_load | 0.02s |
| **08:44:48** | **ONNX start** | — |
| **08:55:26** | **ONNX finish** | **638.50s** |
| 08:55:26 | sentinel_plan_check | 0.03s |
| 08:55:26 | sentinel_chunks | count=1, text_len=1986 |
| **09:00:32** | **Soft time limit (900s) hit** | — |
| 08:59:42 | 2nd attempt started (retry) | — |
| 09:00:15 | 2nd ONNX start | — |
| — | 2nd ONNX finish | — |
| — | Sentinel | — |
| — | Mistral PV | — |
| — | Pipeline completed | — |

### Key findings

1. **ONNX with threads=1: 638.50s** (was 173-304s with AUTO) — 2.3x SLOWER
2. **Soft time limit 900s still hit** — ONNX alone took 638s + Sentinel ~250s = 888s
3. **Retry wasted 540s+** — re-downloads S3, re-runs Gladia, re-runs ONNX
4. **Only 2 speakers, 0 enrolled profiles** — ONNX found nothing, pure waste
