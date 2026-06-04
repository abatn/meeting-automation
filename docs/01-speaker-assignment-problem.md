# Speaker Assignment Problem — Analyse

**Date:** 2026-06-03
**Status:** ✅ Gelöst (Microsoft Teams Architektur)
**Severity:** Critical

---

## Problem

Mistral LLM halluziniert Assignee-Namen die nicht im Meeting waren:
- "AbdulQader Al-Batnini" statt "Abdelkader Batnini" (phonetische Variation)
- "Mohammed Al-Arabi Al-Nakdi" (im Audio erwähnt, aber nicht in DB)
- "Gladia" (Tool-Name, keine Person)
- "N/A", "null" als String

## Root Cause

| Komponente | Problem | Lösung |
|------------|---------|--------|
| **Mistral Prompt** | Text-only "MUST" Regeln ignoriert | Temperature 0.1 + Display Transcript |
| **Validation** | Nur gegen 1-2 resolved_speakers | FULL Participant List + Directory |
| **Fuzzy-Match** | SequenceMatcher für arabische Namen | Double Metaphone phonetisches Matching |
| **Single Speaker** | Fallback entfernt | Reaktiviert mit Confidence Scoring |
| **Speaker vs Assignee** | Vermischt | Getrennt: AssigneeResolver Service |

## Datenquellen

| Quelle | Inhalt | Nutzung |
|--------|--------|---------|
| **ONNX** | Speaker 0 = Abdelkader Batnini (0.90) | Wer GESPROCHEN hat |
| **Gladia** | Full transcript mit Speaker-Tags | Wer was GESAGT hat |
| **Sentinel** | Summary (2-3 Sätze pro Chunk) | PV Overview |
| **DB Participants** | ["Abdelkader Batnini", ...] | Wer im Meeting WAR |
| **DB Users** | Alle Client-User | Directory Resolution |
| **Mistral** | Action extraction + assignee guess | Task-Verständnis |

## Bisherige Lösungsversuche (gescheitert)

1. ❌ Prompt verschärfen → Mistral ignoriert Text-Regeln
2. ❌ Fuzzy-Match allein → SequenceMatcher funktioniert nicht für arabische Transliterationen
3. ❌ Sentinel-Summary → Name verloren
4. ❌ Dual-Context → Besser aber nicht 100%
5. ❌ ONNX als primäre Quelle → ONNX identifiziert wer SPRACH, nicht wer ZUGEWIESEN wird

## Lösung: Microsoft Teams Architektur

Siehe: [[02-speaker-assignment-solution]]

**Kernidee:** Speaker-ID von Assignee-Resolution trennen. AssigneeResolver nutzt:
1. Speaker mappings (wer sprach)
2. Participant List (wer war im Meeting)
3. Phonetic Matching (Double Metaphone)
4. Fuzzy Matching (SequenceMatcher)
5. Single Speaker Fallback
