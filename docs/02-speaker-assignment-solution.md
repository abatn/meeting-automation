# Speaker Assignment Solution — Professioneller Ansatz (Microsoft Teams Architektur)

**Date:** 2026-06-03
**Status:** ✅ Implementiert + E2E-verifiziert (39/39 Tests passed)
**Referenz:** [[01-speaker-assignment-problem]]

---

## Architektur (Microsoft Teams / Zoom / Google Meet Ansatz)

```
Phase 1: Speaker Identification (wer sprach)
  Gladia → ONNX → speaker_mappings = {"Speaker 0": "Abdelkader Batnini"}

Phase 2: Summarization (MAP-Reduce)
  Display Transcript → Sentinel chunks (MAP) → sentinel_summary → Mistral PV (REDUCE)

Phase 3: Action Extraction (wer soll was tun)
  Mistral mit: sentinel_summary + resolved transcript + FULL Participant List → actions

Phase 4: Assignee Resolution (NEU — getrennt von Speaker-ID!)
  AssigneeResolver:
    a. In speaker_mappings? → high confidence (0.95) ✅
    b. In Participant List? → medium confidence (0.75) ✅
    c. Phonetic Match? → lower confidence (0.60) ✅
    d. Fuzzy Match? → lowest confidence (0.50) ✅
    e. Kein Match? → external / manual review
```

## 4-Schichten-Validierung (Microsoft Teams Ansatz)

### Schicht 1: Mistral Prompt (Prävention)

```python
allowed_names = participant_names + [m["resolved_name"] for m in speaker_mappings]

Prompt: "assignee MUST be one of: [Abdelkader Batnini, Mohammed, Fatima]"
        "NEVER use tool names, N/A, or invented names"
        temperature: 0.1 (deterministisch)
```

### Schicht 2: AssigneeResolver (Korrektur)

```python
resolver = AssigneeResolver(
    speaker_mappings=speaker_mappings,    # Wer identifiziert wurde
    participant_names=participant_names,  # Wer im Meeting war
    client_users=client_users,            # Alle Client-User
)

resolution = resolver.resolve(assignee_name, single_speaker=single_speaker)
```

**Resolution Order:**
1. Speaker mappings (phonetic + exact) → user_id
2. Participant list (exact) → user_id
3. Phonetic matching (Double Metaphone) → user_id
4. Fuzzy string matching (SequenceMatcher) → user_id
5. Single speaker fallback → user_id
6. External assignment (email/name)

### Schicht 3: Confidence Scoring (Dokumentation)

| Match Type | Confidence | Beschreibung |
|------------|------------|-------------|
| speaker_mapping | 0.95 | Exakter Match gegen resolved speaker |
| participant_exact | 0.75 | Exakter Match gegen Participant List |
| phonetic | 0.60 | Phonetischer Match (Mohammed/Muhammad) |
| fuzzy | 0.50 | String-Ähnlichkeit (SequenceMatcher) |
| single_speaker_fallback | 0.80 | 1-Speaker-Meeting Fallback |
| external | 0.30 | Kein Match → external |

### Schicht 4: Audit Trail (ISO 27001)

```python
audit_service.log_action(
    action="ACTION_ASSIGNED",
    new_values={
        "assignee_name": assignee,
        "matched_via": "speaker_mapping|phonetic|fuzzy|single_speaker",
        "confidence": 0.95,
        "is_ambiguous": False,
    }
)
```

## Single-Speaker-Regel (REAKTIVIERT)

```
Meeting mit genau 1 Speaker:
  ONNX: Speaker 0 = Abdelkader Batnini (0.90)
  → ALLE Actions ohne validen assignee → Abdelkader Batnini

Meeting mit >1 Speaker:
  → AssigneeResolver gegen alle Speaker + Participants
  → Kein Match → external assignment
```

## Multi-Participant Scenario (1000 Teilnehmer)

| Mistral Output | Validierung | Ergebnis |
|----------------|-------------|----------|
| "Alice" → in Participants | ✅ participant_exact | Behalten (0.75) |
| "Bob" → ONNX Speaker | ✅ speaker_mapping | Behalten (0.95) |
| "Alic" → Fuzzy 0.85 → "Alice" | ✅ fuzzy | Korrigiert (0.50) |
| "Abdulqader" → Phonetic → "Abdelkader" | ✅ phonetic | Korrigiert (0.60) |
| "XyZ" → kein Match, >1 Speaker | ❌ external | External name |
| "Gladia" → invalid | ❌ single_speaker | Fallback |

## Phonetisches Matching (Double Metaphone)

Behandelt arabische Namen-Transliterationen:
- Mohammed / Muhammad / Mohammad → gleicher phonetischer Code
- Abdelkader / Abdulqader / Abd al-Qadir → gleicher phonetischer Code
- Fatima / Fatema / Fatimah → gleicher phonetischer Code

```python
from app.services.phonetic_matcher import phonetic_match

phonetic_match("Mohammed", "Mohammad")  # → 0.85
phonetic_match("Abdelkader", "Abdulqader")  # → 0.75
```

## Dateien

- `backend/app/services/assignee_resolver.py` — **NEU**: Professional AssigneeResolver
- `backend/app/services/phonetic_matcher.py` — **NEU**: Double Metaphone Algorithmus
- `backend/app/tasks/transcription_tasks.py` — AssigneeResolver Integration
- `backend/app/services/pv_service.py` — Temperature 0.1 + Display Transcript
- `backend/tests/e2e/test_assignee_resolver.py` — **NEU**: 27 E2E Tests

## E2E Test-Ergebnisse

```
tests/e2e/test_assignee_resolver.py: 27/27 passed ✅
tests/e2e/test_intelligent_speaker_assignment.py: 12/12 passed ✅
Gesamt: 39/39 passed ✅
```

## Nächste Schritt

Siehe: [[03-implementation-plan]]
