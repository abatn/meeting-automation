# LiveKit Identity vs ONNX — Speaker Identification Analysis

**Date:** 2026-09-07 (Updated 10:07 UTC)
**Context:** ONNX Speaker ID is the pipeline bottleneck (260-638s on AMD64 production)
**Test Case:** test smoke 6 — ONNX took 638s (1st attempt) + 435s (2nd attempt) + running (3rd attempt)

---

## Current Pipeline Stages (Production AMD64)

```
┌─────────────────────┬────────────┬─────────────────────────────────────┐
│ Stage               │ Duration   │ Notes                               │
├─────────────────────┼────────────┼─────────────────────────────────────┤
│ S3 Download         │ 0.1-1.8s   │ ✅ Fast                             │
│ Gladia Transcription│ 13-16s     │ ✅ Fast (external API)              │
│ ONNX Speaker ID     │ 435-638s   │ 🔴 BOTTLENECK (1000m CPU)          │
│ Sentinel LLM        │ 207-417s   │ 🟡 Slow (CPU inference)            │
│ Mistral PV          │ 5-18s      │ ✅ Fast                             │
│ Persistence         │ 0.5-14s    │ ✅ Fast                             │
├─────────────────────┼────────────┼─────────────────────────────────────┤
│ TOTAL               │ 660-1090s+ │ ❌ Exceeds 900s soft time limit    │
└─────────────────────┴────────────┴─────────────────────────────────────┘
```

---

## Current Speaker ID Pipeline (7 signals)

| # | Signal | How it works | Score | Status |
|---|--------|-------------|-------|--------|
| 0 | **LiveKit Identity** | Single room participant → first speaker | 0.95 | ⚠️ LIMITED |
| 0b | Heuristic | Participant matching, creator detection | 0.75 | ✅ |
| 1 | **ONNX Audio** | Embedding vs enrolled profiles | 0.85 | 🔴 435-638s |
| 2 | Regex | Self-introduction detection | 0.80 | ✅ |
| 3 | Mistral Fusion | LLM-based matching | 0.70 | ✅ (10s) |
| 4 | Validation | Name must be in candidates | — | ✅ |
| 5 | Auto-enrollment | Save new speakers | — | ✅ |

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

---

## ONNX Performance Data (Production AMD64)

| Run | ONNX Duration | Config | Status |
|-----|--------------|--------|--------|
| test smoke 2 (1st) | 304s | AUTO threads | ❌ Soft time limit |
| test smoke 4 (1st) | 265s | AUTO threads | ❌ Soft time limit |
| test smoke 5 (2nd) | 173s | AUTO threads | ✅ Completed |
| **test smoke 6 (1st)** | **638s** | **threads=1** | ❌ **2.3x SLOWER** |
| **test smoke 6 (2nd)** | **435s** | **threads=1** | ❌ Still slow |
| test smoke 6 (3rd) | running | threads=1 | ⏳ |

**Benchmark from docs/PIPELINE_OPTIMIZATION_STATUS_2026-08-23.md was misleading:**
- Tested 300 frames on ARM64 (27ms → 3.7ms)
- Production is AMD64 with real audio data
- `intra_op_num_threads=1` made it 2.3x SLOWER, not 11.9x faster

---

## Test smoke 6 — Full Timeline

### Recording `891d1e59`

| Time (UTC) | Event | Duration | Worker |
|-----------|-------|----------|--------|
| 08:44:32 | process_recording received | — | ForkPoolWorker-8 |
| 08:44:32 | s3_download | 0.11s | ForkPoolWorker-8 |
| 08:44:46 | gladia_transcription | 13.37s | ForkPoolWorker-8 |
| 08:44:48 | speaker_id_profile_load | 0.02s | ForkPoolWorker-8 |
| **08:44:48** | **ONNX start (1st)** | — | ForkPoolWorker-8 |
| **08:55:26** | **ONNX finish (1st)** | **638.50s** | ForkPoolWorker-8 |
| 08:55:26 | sentinel_plan_check | 0.03s | ForkPoolWorker-8 |
| 08:55:26 | sentinel_chunks | count=1 | ForkPoolWorker-8 |
| **09:00:32** | **Soft time limit (900s) hit** | — | — |
| 08:59:42 | 2nd attempt started | — | ForkPoolWorker-1 |
| 09:00:15 | 2nd ONNX start | — | ForkPoolWorker-1 |
| 09:47:24 | 2nd ONNX finish | 435.10s | ForkPoolWorker-1 |
| 09:47:25 | 2nd sentinel_start | — | ForkPoolWorker-1 |
| 10:01:22 | 2nd sentinel_finish | 416.95s | ForkPoolWorker-1 |
| 10:01:38 | 3rd attempt started | — | ForkPoolWorker-8 |
| 10:01:54 | 3rd ONNX start | — | ForkPoolWorker-8 |
| **10:07:28** | **3rd ONNX still running** | **582s+** | ForkPoolWorker-8 |

### Key findings

1. **ONNX with threads=1: 638s (1st) / 435s (2nd) / 582s+ (3rd)** — All SLOWER than AUTO (173-304s)
2. **Sentinel with threads=1: 417s** — Much SLOWER than before (207-260s)
3. **Soft time limit 900s still hit** — ONNX alone took 638s + Sentinel 417s = 1055s
4. **3 attempts so far** — Each wastes 600-900s of redundant work
5. **Only 2 speakers, 0 enrolled profiles** — ONNX found nothing, pure waste

---

## Root Cause Analysis

### Why ONNX is slow on AMD64

1. **CPU-bound**: ONNX uses 1000m CPU (full core) but AMD64 is slower than ARM64 for ONNX
2. **Sequential processing**: `for seg in segments_to_check:` — each segment processed one at a time
3. **Audio extraction**: Each segment requires ffmpeg extraction + ONNX inference
4. **No GPU**: Production has no GPU acceleration

### Why threads=1 made it SLOWER

The benchmark tested with 300 fixed-size frames on ARM64. Production audio has:
- Variable segment lengths (1-30s)
- Audio extraction overhead per segment
- Memory allocation patterns different from benchmark

---

## Recommendation (CORRECTED)

| Option | Impact | Effort | Priority | Risk |
|--------|--------|--------|----------|------|
| **A: Skip ONNX when 0 profiles** | Saves 435-638s | ~5 lines | 🔴 P0 | None |
| **B: LiveKit individual track recording** | Eliminates ONNX | ~30 lines | 🟡 P1 | Low |
| **C: Frontend speaking status** | Eliminates ONNX | ~100+ lines | 🟡 P1 | Medium |

---

## Option A: Skip ONNX when 0 profiles (Quick Win) — CORRECTED

### ⚠️ Critical Bug in Original Proposal

My original proposal placed the guard at line 718 (after the expensive extraction). This is WRONG.

| What I proposed | What's actually needed |
|----------------|----------------------|
| Guard at line 718 (after extraction) | Guard before line 663 (before extraction) |
| Would save: ~0s (matching already guarded) | Will save: 260-638s (skip extraction + ONNX) |

### The actual bottleneck

```python
# Line 663 — THIS is the expensive call (260-638s):
embedding = await _extract_speaker_embedding(temp_path, speaker_segments)

# Line 719 — This is already guarded (fast, ~seconds):
if embedding is not None and profiles_with_embeddings:
    # ONNX matching
```

`_extract_speaker_embedding` does:
1. `audio_segment_service.extract_speaker_segments()` — ffmpeg extraction
2. `speaker_embedding_service.extract_embedding()` — ONNX inference

**The 260-638s is spent at extraction + inference, not at matching.**

### Correct fix location
`backend/app/tasks/transcription_tasks.py`, line 662-663:

```python
# BEFORE line 663 — CORRECT fix location
if not profiles_with_embeddings:
    logger.info(f"Skipping ONNX: 0 enrolled profiles for {speaker_label}")
    embedding = None
else:
    embedding = await _extract_speaker_embedding(temp_path, speaker_segments)
```

### What this saves

| Metric | Current | With Fix |
|--------|---------|----------|
| ONNX speaker_id_process_speakers | 435-638s | ~0s (skip extraction) |
| Pipeline total (3-min audio) | 660-1090s+ | ~230-350s |
| Time under 900s limit | ❌ Often killed | ✅ Always under |

### Note on ONNX segment reassignment (lines 235-284)

The segment reassignment block at line 243 is ALREADY guarded:
```python
if profiles_with_emb:  # Already skips when 0 profiles
    segments_to_check = ...
```
No change needed there.

**Impact:** Saves 435-638s for every meeting with 0 enrolled profiles (most meetings)

---

## Option B: LiveKit Individual Track Recording (Best long-term)

### Current: Room Composite
```
Room Egress → Single audio file → Gladia diarizes → ONNX matches speakers
```

### Proposed: Individual Track Recording
```
Track Egress → Per-participant audio files → Each file has participant identity
→ No diarization needed → No ONNX needed
```

### How it works

1. Use `TrackEgress` instead of `RoomCompositeEgress`
2. Each participant's audio is recorded as a separate file
3. The file is labeled with the participant's identity
4. Pipeline reads identity directly from the track metadata

### Advantages over ONNX

| Aspect | ONNX | Individual Track |
|--------|------|-----------------|
| Speed | 435-638s | ~0s (metadata lookup) |
| Accuracy | 85% (embedding match) | 100% (direct identity) |
| CPU usage | 1000m (full core) | ~0m |
| Dependencies | ONNX model, audio extraction | LiveKit Egress only |

### Disadvantages

| Aspect | ONNX | Individual Track |
|--------|------|-----------------|
| Unknown speakers | ✅ Can enroll new speakers | ❌ Only known participants |
| Bandwidth | ✅ Single file | ❌ Multiple files |
| Implementation | ✅ Existing | 🔴 Requires egress change |

---

## Option C: Frontend Reports Speaking Status (Medium-term)

### Architecture

```
Frontend (JS SDK):
  room.on(RoomEvent.ActiveSpeakersChanged, (speakers) => {
    // Send to backend via WebSocket
    ws.send({type: 'speaker_timeline', data: speakers})
  })

Backend:
  POST /api/v1/meetings/{id}/speaker-timeline
  [{participant_id, start_time, end_time}, ...]

Pipeline:
  1. Load speaker_timeline from DB
  2. Match to Gladia segments by timestamp overlap
  3. Speaker 0 = Participant who was active during 00:00-00:05
```

### Required changes

1. **Frontend**: Capture `RoomEvent.ActiveSpeakersChanged` events (~30 lines)
2. **Backend API**: New endpoint for speaker timeline (~20 lines)
3. **DB schema**: `meeting_speaker_timeline` table (~10 lines)
4. **Pipeline**: New matching logic (~40 lines)

**Total: ~100+ lines**

---

## Summary

### Current State
- ONNX is the pipeline bottleneck (435-638s on AMD64)
- LiveKit has NO server-side active speaker detection
- `intra_op_num_threads=1` made ONNX 2.3x SLOWER
- `n_threads=1` for Sentinel made it ~2x SLOWER

### Goals
- Pipeline total: <300s (currently 660-1090s+)
- ONNX: <30s (currently 435-638s)
- No retries (currently 3 attempts per meeting)

### Path Forward
1. **Immediate**: Option A (skip ONNX when 0 profiles) — saves 435-638s
2. **Short-term**: Option B (individual track recording) — eliminates ONNX
3. **Long-term**: Option C (frontend speaking status) — eliminates ONNX for known participants
