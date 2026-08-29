# Pipeline Quick Wins (1-2 hrs, Existing Stack)

| # | Fix | File | Gain |
|---|-----|------|------|
| 1 | Adaptive Gladia polling: 1s→2s→3s→5s (max 30s total for short audio) | `gladia_service.py:75-95` | ~60-80s |
| 2 | Start S3 download before `delay()` in `recording_service.after_upload()` | `recording_service.py:78-83` | ~5-10s overlap |
| 3 | Remove `await asyncio.sleep(0.1)` in speaker batch loop; batch size 5→8 | `transcription_tasks.py:612-614` | ~5-10s |
| 4 | Celery: `prefetch_multiplier=1`, `task_acks_late=True`, `concurrency=CPU*2` | `celery_app.py` | throughput |

---

## Context

**Problem**: 30-second audio takes ~2:40 min total processing time
- Recording (Egress): 27s
- **Transcription (Gladia polling): 1:53 min** ← **Main bottleneck**
- Speaker-ID: <1s
- PV + Actions: <1s

**Root cause**: Fixed 5s polling interval in `gladia_service.py:77` → 22 cycles × 5s = **110s idle wait** for 30s audio.

---

## Quick Wins Implementation Order

### 1. Adaptive Gladia Polling (Highest Impact)
**File**: `gladia_service.py:75-95`

Current: Fixed `await asyncio.sleep(5)`  
Proposed: Adaptive backoff: 1s → 2s → 3s → 5s (cap at 30s total for short audio < 60s)

```python
# Current (line ~77)
await asyncio.sleep(5)

# Proposed
poll_interval = 1
max_interval = 5
total_waited = 0
max_total_wait = 30  # seconds for short audio

while not done:
    await asyncio.sleep(poll_interval)
    total_waited += poll_interval
    poll_interval = min(poll_interval + 1, max_interval)
    if total_waited >= max_total_wait:
        poll_interval = max_interval
```

**Est. Gain**: ~60-80s (eliminates ~110s idle polling for 30s audio)

---

### 2. Early S3 Download
**File**: `recording_service.py:78-83` (`after_upload` method)

Move `_download_audio()` call **before** `transcription_tasks._process_recording_pipeline.delay()` so download overlaps with Gladia upload/processing.

---

### 3. Speaker Batch Optimization
**File**: `transcription_tasks.py:612-614`

Remove artificial delay:
```python
# Remove this line:
await asyncio.sleep(0.1)

# Increase batch size from 3 to 8
BATCH_SIZE = 8
```

---

### 4. Celery Tuning
**File**: `celery_app.py`

Add to Celery config:
```python
app.conf.update(
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_concurrency=os.cpu_count() * 2,
)
```

---

## Expected Result

| Metric | Before | After (Projected) |
|--------|--------|-------------------|
| Total pipeline (30s audio) | ~2:40 min | **~45-60s** |
| Gladia polling waste | ~110s | ~10-20s |
| Sequential overhead | ~30s | ~10s |

---

## Medium Wins (Next Sprint)

| # | Fix | Gain |
|---|-----|------|
| 5 | Overlap Speaker ID embedding extraction with Gladia polling | ~20-30s |
| 6 | Parallelize Mistral Reduce (summary/decisions/actions) | ~5-10s |