# Fix: Speaker Names in PV (Procès-Verbal) — Microsoft Teams Architektur

## Problem
Das von Mistral generierte PV enthielt "Speaker 0", "Speaker 1" statt echter Namen wie "Ahmed", "Fatima".
Task-Zuweisungen zeigten "N/A" bei Namensvarianten ("AbdulQader Al-Batnini" ≠ "Abdelkader Batnini").

## Root Causes
1. **Mistral sah "Speaker 0"** statt "Abdelkader Batnini" im Transcript
2. **Kein phonetisches Matching**: "Abdulqader" ≠ "Abdelkader" → SequenceMatcher versagt bei arabischen Transliterationen
3. **Validation nur gegen resolved_speakers** → Participant List ignoriert
4. **Single-Speaker-Fallback entfernt** → Keine Sicherheit für 1-Speaker-Meetings
5. **Temperature 0.7** → Mistral zu kreativ bei Namen

## Lösung (Microsoft Teams Architektur)

### 1. Display Transcript statt Original (`transcription_tasks.py`)
```python
# VORHER: Mistral sah "Speaker 0: ..."
full_transcript=original_transcript

# NACHHER: Mistral sieht "Abdelkader Batnini: ..."
full_transcript=display_text  # Mit aufgelösten Namen
```

### 2. AssigneeResolver Service (`assignee_resolver.py`)
```python
# 5-stufige Resolution:
# 1. Speaker mappings (0.95)
# 2. Participant list exact (0.75)
# 3. Phonetic matching (0.60)
# 4. Fuzzy string matching (0.50)
# 5. Single speaker fallback (0.80)

resolver = AssigneeResolver(
    speaker_mappings=speaker_mappings,
    participant_names=participant_names,
    client_users=client_users,  # NEU: Alle Client-User
)
resolution = resolver.resolve(assignee_name, single_speaker=single_speaker)
```

### 3. Double Metaphone Phonetics (`phonetic_matcher.py`)
```python
# Arabische Namen-Transliterationen:
phonetic_match("Mohammed", "Mohammad")  # → 0.85
phonetic_match("Abdelkader", "Abdulqader")  # → 0.75
phonetic_match("Fatima", "Fatema")  # → 0.80
```

### 4. Single Speaker Fallback (REAKTIVIERT)
```python
if single_speaker:
    return self._resolve_to_speaker(single_speaker, "single_speaker_fallback")
```

### 5. Mistral Temperature 0.1
```python
payload = {
    "model": "mistral-large-latest",
    "temperature": 0.1,  # Deterministisch
    ...
}
```

## Test-Ergebnisse (Docker Container)

### Alle Tests — 39/39 PASSED
```
tests/e2e/test_assignee_resolver.py — 27/27 PASSED
tests/e2e/test_intelligent_speaker_assignment.py — 12/12 PASSED
=============== 39 passed, 27 warnings in 33.61s ===============
```

## Geänderte Dateien

| Datei | Änderung | Zeilen |
|-------|----------|--------|
| `app/services/phonetic_matcher.py` | **NEU**: Double Metaphone | +300 |
| `app/services/assignee_resolver.py` | **NEU**: AssigneeResolver | +340 |
| `app/tasks/transcription_tasks.py` | AssigneeResolver Integration | ~150 ersetzt |
| `app/services/pv_service.py` | Temperature 0.1 + Display Transcript | +5 |
| `tests/e2e/test_assignee_resolver.py` | **NEU**: 27 Tests | +250 |

## Wirkung

| Vorher | Nachher |
|--------|---------|
| `"Speaker 0: Hallo"` | `"Abdelkader Batnini: Hallo"` |
| PV: "Speaker 0 diskutierte Budget" | PV: "Abdelkader diskutierte Budget" |
| DB-Segmente: `"speaker": "Speaker 0"` | DB-Segmente: `"speaker": "Abdelkader Batnini"` |
| "Abdulqader" → external_name | "Abdulqader" → phonetic → "Abdelkader" ✅ |
| Single Speaker → external | Single Speaker → fallback ✅ |
| Temperature 0.7 → Halluzination | Temperature 0.1 → deterministisch |

## Edge Cases

- **Leeres `speaker_mappings`** → Resolver nutzt Participant List + Users
- **`resolved_name = None`** → Wird gefiltert, Original-Label bleibt
- **Confidence < 0.50** → Name wird nicht ersetzt (verhindert falsche Zuordnung)
- **Unbekannte Speaker** → Bleiben als "Speaker N" erhalten
- **Ambiguous matches** → External assignment mit `is_ambiguous=True`

---

## Fix 2026-06-05: Speaker Resolution — 3 weitere Bugs

### Problem
PV zeigte weiterhin `"speaker 0"` bei einer Action (4 von 4). `learn_from_feedback` erstellte External-Zuordnungen mit `"Speaker 0"` statt echte Namen.

### Root Cause (3 Bugs)

**Bug #1 — `match_speaker()` gab `profile.name` statt `profile.resolved_name` zurück**
```python
# speaker_profile_service.py:164
best_name = profile.name           # → "Speaker 0" (Gladia-Label)
# Fix:
best_name = profile.resolved_name or profile.name  # → "Abdelkader Batnini"
```

**Bug #2 — `learn_from_feedback` fand das Profil nicht**
```python
# action_service.py:747
# VORHER: Nur nach meeting_id gefiltert (Profil hatte meeting_id=NULL)
speaker_stmt = select(Speaker).where(Speaker.meeting_id == suggestion.meeting_id)
# Fix: client_id + meeting_id IS NULL Fallback
speaker_stmt = select(Speaker).where(
    Speaker.client_id == client_id,
    or_(Speaker.meeting_id == suggestion.meeting_id, Speaker.meeting_id.is_(None))
)
```

**Bug #3 — Kandidaten enthielten "Speaker 0"**
```python
# transcription_tasks.py:388 + action_service.py:511
# VORHER:
profile_names = [p.name for p in enrolled_profiles if p.name]
# → ["Speaker 0"]
# Fix:
profile_names = [p.resolved_name or p.name for p in enrolled_profiles if p.resolved_name or p.name]
# → ["Abdelkader Batnini"]
```

### Test-Ergebnisse
```
tests/e2e/test_intelligent_speaker_assignment.py — 16/16 PASSED
tests/security/ — 20/20 PASSED
tests/test_meetings.py — 2/2 PASSED
```

### Geänderte Dateien
| Datei | Zeile | Änderung |
|-------|-------|----------|
| `app/services/speaker_profile_service.py` | 164 | `profile.resolved_name or profile.name` |
| `app/services/action_service.py` | 747-749 | Query mit `client_id` + `meeting_id IS NULL` |
| `app/tasks/transcription_tasks.py` | 388 | `p.resolved_name or p.name` |
| `app/services/action_service.py` | 511 | `p.resolved_name or p.name` |
