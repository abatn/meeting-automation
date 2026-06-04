# Intelligent Speaker Assignment via Speaker Mappings

**Date:** 2026-06-03
**Status:** ✅ Completed (Microsoft Teams Architektur)
**Tests:** 43/43 passed (E2E in Docker container)

---

## Problem

Die bestehende Pipeline ignorierte `speaker_mappings` während der Task-Zuweisung. Stattdessen wurde nur ILIKE/fuzzy Matching gegen alle Users durchgeführt, was die wertvolle Speaker-Identification-Arbeit verlor.

Zusätzlich: `learn_from_feedback()` erstellte immer `external_name` Assignments, ohne bestehende Users zu prüfen.

### CRITICAL RULES — Keine Fake/Mock/Null/Empty Assignees

| Verboten | Grund |
|----------|-------|
| `suggested_assignee: null` | Mistral MUSS einen Namen aus der CLOSED LIST zuweisen |
| `suggested_assignee: ""` (leer) | Jede Action braucht einen Assignee |
| `suggested_assignee: "N/A"` | Kein Platzhalter erlaubt |
| `suggested_assignee: "Speaker 0"` | Gladia Labels sind keine Personen |
| Erfundene Namen | Nur CLOSED LIST (Participant Names) erlaubt |
| Transliterationen | EXACT MATCH der definierten Namen |

## Lösung: AssigneeResolver (Microsoft Teams Ansatz)

### 1. Professional AssigneeResolver (`assignee_resolver.py`)

**NEU:** Separater Service der Speaker-ID von Assignee-Resolution trennt.

```python
resolver = AssigneeResolver(
    speaker_mappings=speaker_mappings,    # Wer identifiziert wurde
    participant_names=participant_names,  # Wer im Meeting war
    client_users=client_users,            # Alle Client-User
)

resolution = resolver.resolve(assignee_name, single_speaker=single_speaker)
```

**Resolution Order:**
1. Speaker mappings (exact + phonetic) → user_id (0.95)
2. Participant list (exact) → user_id (0.75)
3. Phonetic matching (Double Metaphone) → user_id (0.60)
4. Fuzzy string matching → user_id (0.50)
5. Single speaker fallback → user_id (0.80)
6. External assignment (email/name) (0.30)

### 2. Phonetic Matching (`phonetic_matcher.py`)

**NEU:** Double Metaphone Algorithmus für arabische Namen-Transliterationen.

```python
phonetic_match("Mohammed", "Mohammad")  # → 0.85
phonetic_match("Abdelkader", "Abdulqader")  # → 0.75
```

### 3. Display Transcript statt Original

**Änderung:** Mistral sieht jetzt `"Abdelkader Batnini: ..."` statt `"Speaker 0: ..."`.

```python
# VORHER:
full_transcript=original_transcript  # "Speaker 0: ..."

# NACHHER:
full_transcript=display_text  # "Abdelkader Batnini: ..."
```

### 4. Mistral Temperature

**Änderung:** Temperature 0.1 für deterministische Ausgabe.

```python
payload = {
    "model": "mistral-large-latest",
    "temperature": 0.1,  # NEU
    ...
}
```

### 5. Single Speaker Fallback (REAKTIVIERT)

```python
if single_speaker:
    return self._resolve_to_speaker(single_speaker, "single_speaker_fallback")
```

## Dateien Geändert

| Datei | Änderungen | Zeilen |
|-------|-----------|--------|
| `backend/app/services/assignee_resolver.py` | **NEU**: AssigneeResolver Service | +340 |
| `backend/app/services/phonetic_matcher.py` | **NEU**: Double Metaphone | +300 |
| `backend/app/tasks/transcription_tasks.py` | AssigneeResolver Integration | ~150 ersetzt |
| `backend/app/services/pv_service.py` | Temperature 0.1 + Display Transcript | +5 |
| `backend/app/models/transcription.py` | `resolved_name` Column zu Speaker | +1 |
| `backend/app/services/action_service.py` | generate_suggestions + learn_from_feedback CRITICAL RULES | ~80 |
| `backend/app/services/speaker_profile_service.py` | speaker_label + resolved_name Parameter | ~10 |
| `backend/app/services/auto_enrollment_service.py` | resolved_name beim Erstellen setzen | +2 |
| `backend/tests/e2e/test_assignee_resolver.py` | **NEU**: 27 E2E Tests | +250 |
| `backend/tests/e2e/test_intelligent_speaker_assignment.py` | 4 neue Tests + Updates | +180 |

## Test-Ergebnisse

```
tests/e2e/test_assignee_resolver.py: 27/27 passed ✅
tests/e2e/test_intelligent_speaker_assignment.py: 16/16 passed ✅
Gesamt: 43/43 passed ✅
```

## Architektur Impact

| Aspekt | Vorher | Nachher |
|--------|--------|---------|
| Assignment Basis | ILIKE gegen alle Users | AssigneeResolver (5-stufig) |
| Name Matching | SequenceMatcher | Double Metaphone + SequenceMatcher |
| Candidate List | resolved_speakers only | speakers + participants + all users |
| Single Speaker | Entfernt | Reaktiviert |
| Transcript für Mistral | Original (Speaker 0) | Display (mit Namen) |
| Temperature | Default (0.7) | 0.1 |
| Confidence Scoring | Binär | 6-stufig (0.30-0.95) |
| Neue Services | 0 | 2 (AssigneeResolver, PhoneticMatcher) |

## How to Run Tests

```bash
# Neue Tests
docker compose exec backend pytest tests/e2e/test_assignee_resolver.py -v

# Regression Tests
docker compose exec backend pytest tests/e2e/test_intelligent_speaker_assignment.py -v

# Alle Tests
docker compose exec backend pytest tests/e2e/test_assignee_resolver.py tests/e2e/test_intelligent_speaker_assignment.py -v
```
