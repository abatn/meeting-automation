# Phase 7: Suggestion Pipeline — CRITICAL RULES

**Date:** 2026-06-03
**Status:** ✅ Completed
**Tests:** 43/43 passed (E2E in Docker container)

---

## CRITICAL RULE: NULL/EMPTY ASSIGNEES ARE FORBIDDEN

In der gesamten Pipeline — von Mistral über Suggestions bis learn_from_feedback — ist es **VERBOTEN** Assignees auf null, leer, "N/A", "TBD" oder irgendeinen Platzhalter zu setzen.

### Verbotene Werte

| Wert | Status |
|------|--------|
| `null` | ❌ VERBOTEN |
| `""` (leer) | ❌ VERBOTEN |
| `"N/A"` | ❌ VERBOTEN |
| `"TBD"` / `"TBA"` | ❌ VERBOTEN |
| `"null"` (String) | ❌ VERBOTEN |
| `"non défini"` | ❌ VERBOTEN |
| `"undefined"` | ❌ VERBOTEN |
| `"Speaker 0"` (Gladia Label) | ❌ VERBOTEN |
| Erfundene Namen | ❌ VERBOTEN |

### Pflicht-Regeln

1. **JEDE Action MUSS einen Assignee haben** — kein "unassigned" erlaubt
2. **CLOSED LIST** — Nur Namen aus der Participant List dürfen verwendet werden
3. **EXACT MATCH** — Keine Varianten, Transliterationen oder Abkürzungen
4. **AUTO-RESOLVE** — Wenn Mistral null liefert, wird automatisch aufgelöst
5. **FALLBACK-KETTE** — Transcript-Segment → Single Speaker → Erster Participant

---

## Implementierung

### 1. Mistral Prompt (generate_suggestions)

**Datei:** `backend/app/services/action_service.py`

Der Prompt enthält explizite CRITICAL RULES:

```
CRITICAL RULES FOR ASSIGNEE ASSIGNMENT:
1. CLOSED LIST: You MUST assign EVERY action to a person from this list: [Names]
2. NO NULL: NEVER return null, empty, "N/A", "TBD", or any placeholder.
3. NO INVENTION: NEVER invent names not in the closed list.
4. EXACT MATCH: Use the EXACT name as written in the closed list above.
5. SINGLE PERSON: If only one person is mentioned, assign all actions to that person.
6. EVERY ACTION MUST HAVE AN ASSIGNEE: There is no such thing as an unassigned action.
```

### 2. Post-Response Validation (generate_suggestions)

Nach Mistral Response wird JEDE Suggestion validiert:

```python
INVALID_ASSIGNEES = {"n/a", "null", "none", "non défini", "undefined", ...}

if raw_assignee in INVALID_ASSIGNEES:
    # Auto-resolve via transcript segment keyword match
    # → Single speaker fallback
    # → First participant fallback (NIEMALS null)
```

### 3. learn_from_feedback Resolution

**Datei:** `backend/app/services/action_service.py`

Mandatory Resolution — kein Skip, kein null:

```python
# CRITICAL RULE: NULL/EMPTY ASSIGNEES ARE FORBIDDEN
# Every action MUST have an assignee. Resolution is MANDATORY.

# Priority order:
# 1. Valid suggested_assignee from Mistral
# 2. Transcript segment keyword match (who spoke about this topic?)
# 3. Single speaker fallback
# 4. First participant fallback (last resort — never null)

if not assignee_name:
    logger.critical("[ASSIGNEE_CRITICAL] No assignee resolved — NEVER happen")
    await self.db.commit()
    return  # Bug — aber kein null assignment erstellt
```

### 4. Speaker.resolved_name

**Datei:** `backend/app/models/transcription.py`

Speaker Tabelle trennt Gladia Label von resolvedem Namen:

```python
name = Column(String)           # "Speaker 0" (Gladia Label)
resolved_name = Column(String)  # "Abdelkader Batnini" (ONNX+Mistral)
```

**Migration:** `alembic/versions/f1a2b3c4d5e6_add_resolved_name_to_speakers.py`

---

## Datenquellen die kombiniert werden

| Quelle | Inhalt | Nutzung |
|--------|--------|---------|
| **Gladia** | Full transcript mit Speaker-Tags | Wer was gesagt hat |
| **ONNX** | Speaker 0 = Abdelkader (0.90) | Wer GESPROCHEN hat |
| **DB Participants** | ["Abdelkader", "Mohamed"] | CLOSED LIST |
| **DB Users** | Alle Client-User | Directory Resolution |
| **Speaker.resolved_name** | "Speaker 0" → "Abdelkader" | Label-to-Name Mapping |
| **Transcript Segments** | Keyword-Overlap mit Task | Wer hat über Thema gesprochen? |

---

## Test-Ergebnisse

```
tests/e2e/test_assignee_resolver.py: 27/27 passed ✅
tests/e2e/test_intelligent_speaker_assignment.py: 16/16 passed ✅
Gesamt: 43/43 passed ✅
```

### Neue Tests

| Test | Prüft |
|------|-------|
| `test_speaker_resolved_name_column` | Speaker.name ≠ Speaker.resolved_name |
| `test_learn_from_feedback_null_assignee_single_speaker` | Single Speaker Fallback bei null |
| `test_learn_from_feedback_uses_resolved_name` | resolved_name wird korrekt genutzt |
| `test_learn_from_feedback_transcript_segment_match` | Transcript-Segment-Suche funktioniert |

---

## Dateien Geändert

| Datei | Änderung |
|-------|----------|
| `backend/app/models/transcription.py` | `resolved_name` Column zu Speaker |
| `backend/app/services/speaker_profile_service.py` | create_profile + get_profile_by_name erweitert |
| `backend/app/services/auto_enrollment_service.py` | speaker_label + resolved_name Parameter |
| `backend/app/services/action_service.py` | generate_suggestions + learn_from_feedback CRITICAL RULES |
| `backend/alembic/versions/f1a2b3c4d5e6_...` | DB Migration für resolved_name |
| `backend/tests/e2e/test_intelligent_speaker_assignment.py` | 4 neue Tests |
