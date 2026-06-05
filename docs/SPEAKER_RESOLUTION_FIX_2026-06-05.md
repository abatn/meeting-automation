# Speaker Resolution Fix — 2026-06-05

## Problem
PV showed `"speaker 0"` instead of real participant names (e.g., "Abdelkader Batnini") in action assignments.

## Root Cause Analysis

### DB State
- Single speaker profile: `name="Speaker 0"`, `resolved_name="Abdelkader Batnini"`, `meeting_id=NULL`
- Transcription segments: all `"speaker": "Speaker 0"` (Gladia detected only 1 speaker)
- 8 actions created: 3 correct names, 5 with "Speaker 0"

### 3 Interconnected Bugs

**Bug #1 — `match_speaker()` returned wrong field**
```python
# speaker_profile_service.py:164
best_name = profile.name           # → "Speaker 0" (Gladia label)
# Fixed:
best_name = profile.resolved_name or profile.name  # → "Abdelkader Batnini"
```
- `speaker_mappings` got `resolved_name="Speaker 0"` instead of `"Abdelkader Batnini"`
- `name_map` became `{"Speaker 0": "Speaker 0"}` — no replacement in transcript
- Mistral context: `"Speaker 0 = Speaker 0"` — no real name

**Bug #2 — `learn_from_feedback` couldn't find the profile**
```python
# action_service.py:747
speaker_stmt = select(Speaker).where(Speaker.meeting_id == suggestion.meeting_id)
# Profile had meeting_id=NULL → query returned empty → speaker_mappings=[]
# Fixed: added client_id filter + meeting_id IS NULL fallback
speaker_stmt = select(Speaker).where(
    Speaker.client_id == client_id,
    or_(Speaker.meeting_id == suggestion.meeting_id, Speaker.meeting_id.is_(None))
)
```

**Bug #3 — Candidates contained "Speaker 0"**
```python
# transcription_tasks.py:388 AND action_service.py:511
profile_names = [p.name for p in enrolled_profiles if p.name]
# → ["Speaker 0"] — Gladia label in candidate list!
# Fixed:
profile_names = [p.resolved_name or p.name for p in enrolled_profiles if p.resolved_name or p.name]
```

## Fixes Applied

| # | File | Line | Change |
|---|------|------|--------|
| 1 | `speaker_profile_service.py` | 164 | `profile.resolved_name or profile.name` |
| 2 | `action_service.py` | 747-749 | Query: `Speaker.client_id == client_id` + `or_(meeting_id == ..., meeting_id.is_(None))` |
| 3a | `transcription_tasks.py` | 388 | `p.resolved_name or p.name` for candidates |
| 3b | `action_service.py` | 511 | `p.resolved_name or p.name` for candidates |

## Test Results
- Speaker assignment tests: **16/16 passed**
- Security tests: **20/20 passed**
- Meetings tests: **2/2 passed**

## Pipeline Flow After Fix
1. `match_speaker()` returns `"Abdelkader Batnini"` (resolved_name)
2. `speaker_mappings` has `resolved_name="Abdelkader Batnini"`
3. `name_map` becomes `{"Speaker 0": "Abdelkader Batnini"}`
4. Display transcript: `"Abdelkader Batnini:"` instead of `"Speaker 0:"`
5. Mistral PV context: `"Speaker 0 = Abdelkader Batnini"`
6. All 4 actions assigned to correct names
7. `learn_from_feedback` finds profile via client_id + meeting_id IS NULL
8. Candidates: `["Abdelkader Batnini", "Taoufik Batnini", "mohamed el arbi el nakti"]`
