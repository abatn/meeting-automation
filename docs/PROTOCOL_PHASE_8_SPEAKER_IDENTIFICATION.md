# Phase 8: Speaker Identification — Architektur & Implementierung

**Datum:** 2026-06-03
**Status:** ✅ Abgeschlossen (Microsoft Teams Architektur)
**Ziel:** Automatische Zuordnung von Speaker-Labels zu echten Namen + professionelle Assignee-Resolution.

---

## 1. Überblick

### Problem
Gladia liefert Diarisierung mit generischen Labels (`Speaker 0`, `Speaker 1`). Für nutzbare Transkripte müssen diese echten Namen zugeordnet werden. Zusätzlich: Mistral halluziniert Assignee-Namen bei Action-Extraktion.

### Lösung
Hybrider Ansatz mit **getrennter Speaker-ID und Assignee-Resolution** (Microsoft Teams Architektur):
- **Speaker-ID:** Audio-Embedding-Matching + Text-Inferenz (ONNX + Regex + Mistral Fusion)
- **Assignee-Resolution:** AssigneeResolver mit phonetischem Matching (Double Metaphone)

### Design-Entscheidungen
| Entscheidung | Begründung |
|---|---|
| Speaker-ID von Assignee-Resolution getrennt | Wer sprach ≠ wer ist zugewiesen |
| Double Metaphone für Namen | Arabische Transliterationen (Mohammed/Muhammad) |
| FULL Participant List als Quelle | Nicht nur resolved_speakers |
| Single Speaker Fallback reaktiviert | Einfachster Fall: 1 Speaker = alle Tasks |
| Display Transcript für Mistral | Mistral sieht echte Namen, nicht "Speaker 0" |
| Temperature 0.1 | Deterministische Ausgabe |

---

## 2. Architektur

```
┌─────────────────────────────────────────────────────────────┐
│  GLADIA V2                                                   │
│  Output: utterances + diarization                           │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  AUDIO-SEGMENT-EXTRAKTION (ffmpeg)                           │
│  - Pro Speaker: Alle Utterances → Audio-Segmente             │
│  - Auf 16 kHz Mono resampeln                                 │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  EMBEDDING-EXTRAKTION (ONNX Runtime)                        │
│  - Modell: ecapa-speaker-v1.onnx (80 MB)                    │
│  - Output: 192-dim Embedding pro Speaker                     │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  SPEAKER-ID: Cosine Distance + Regex + Mistral Fusion        │
│  - Cosine Distance zu gespeicherten Profilen                 │
│  - Regex Self-Introduction (4 Sprachen)                      │
│  - Mistral Fusion mit Candidate List                         │
│  Output: speaker_mappings = {"Speaker 0": "Abdelkader"}      │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  DISPLAY TRANSCRIPT: "Speaker 0" → "Abdelkader Batnini"      │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  SENTINEL (MAP) → MISTRAL PV (REDUCE)                        │
│  Input: Display Transcript (mit Namen)                       │
│  Temperature: 0.1                                            │
│  Output: PV mit Actions + Assignees                          │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  ASSIGNEE RESOLUTION (NEU — getrennt von Speaker-ID!)        │
│  AssigneeResolver:                                           │
│  1. Speaker mappings (0.95)                                  │
│  2. Participant list exact (0.75)                            │
│  3. Phonetic matching - Double Metaphone (0.60)              │
│  4. Fuzzy string matching (0.50)                             │
│  5. Single speaker fallback (0.80)                           │
│  6. External assignment (0.30)                               │
└─────────────────────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  AUTOMATISCHES ENROLLMENT                                    │
│  - Bestätigte Matches → gleitender Mittelwert                │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Komponenten

### 3.1 SpeakerEmbeddingService
**Datei:** `backend/app/services/speaker_embedding_service.py`
- ONNX Runtime für CPU-Inferenz
- 192-dim Embedding-Vektor pro Audio-Segment
- L2-normalisiert

### 3.2 SpeakerProfileService
**Datei:** `backend/app/services/speaker_profile_service.py`
- Cosine Distance: `1.0 - np.dot(embedding, stored)`
- Thresholds: HIGH < 0.10, MEDIUM < 0.25, LOW < 0.40
- Running average für Embedding-Updates

### 3.3 AssigneeResolver (NEU)
**Datei:** `backend/app/services/assignee_resolver.py`
- 5-stufige Resolution
- Confidence Scoring (0.30-0.95)
- Ambiguity Detection
- Single Speaker Fallback

### 3.4 PhoneticMatcher (NEU)
**Datei:** `backend/app/services/phonetic_matcher.py`
- Double Metaphone Algorithmus
- Arabische Namen-Transliterationen
- Phonetically similar names: Mohammed/Muhammad, Abdelkader/Abdulqader

### 3.5 Datenbank-Erweiterung
**Tabelle:** `speakers` (bestehende Tabelle)

Neue Spalten:
| Spalte | Typ | Beschreibung |
|---|---|---|
| `client_id` | String | Multi-Tenant-Isolation |
| `embedding` | JSON | 192-dim Float-Array |
| `sample_count` | Integer | Anzahl Samples im Mittelwert |
| `mapping_confidence` | Float | 0.0–1.0 |
| `mapping_method` | String | embedding/text_inference/manual/hybrid |
| `source` | String | auto_enrolled/manual/auto_confirmed |

---

## 4. Ressourcen

### 4.1 Modell-Dateien
| Datei | Größe | Pfad |
|---|---|---|
| `ecapa-speaker-v1.onnx` | 80 MB | `backend/app/models/speaker_embeddings/` |
| `fbank-80x201-f32.bin` | 64 KB | `backend/app/models/speaker_embeddings/` |

### 4.2 Neue Abhängigkeiten
| Package | Version | Zweck |
|---|---|---|
| `onnxruntime` | 1.19.2 | ONNX-Modell-Inferenz (CPU) |
| `librosa` | 0.10.2.post1 | Audio-Laden + fbank-Features |

---

## 5. Schwellenwerte

### Speaker-ID (Cosine Distance)
| Confidence | Cosine Distance | Aktion |
|---|---|---|
| HIGH | < 0.10 | Automatische Zuordnung |
| MEDIUM | 0.10–0.25 | Vorschlag in UI |
| LOW | 0.25–0.40 | Nur Hinweis |
| NO MATCH | > 0.40 | Unbekannter Sprecher |

### Assignee Resolution (Confidence)
| Match Type | Confidence | Beschreibung |
|---|---|---|
| speaker_mapping | 0.95 | Exakter Match gegen resolved speaker |
| participant_exact | 0.75 | Exakter Match gegen Participant List |
| phonetic | 0.60 | Phonetischer Match (Double Metaphone) |
| fuzzy | 0.50 | String-Ähnlichkeit (SequenceMatcher) |
| single_speaker | 0.80 | 1-Speaker-Meeting Fallback |
| external | 0.30 | Kein Match → external |

---

## 6. E2E-Test-Ergebnisse

```
tests/e2e/test_assignee_resolver.py: 27/27 passed ✅
tests/e2e/test_intelligent_speaker_assignment.py: 12/12 passed ✅
Gesamt: 39/39 passed ✅
```

---

## 7. Implementierungsstatus

- [x] **Phase 1:** ONNX-Modell + librosa in requirements.txt, Docker-Image
- [x] **Phase 2:** Speaker-Tabelle erweitert, SpeakerProfile-Service
- [x] **Phase 3:** Audio-Segment-Extraktion (ffmpeg) + Embedding-Pipeline
- [x] **Phase 4:** Cosine Distance Matching + Schwellenwert-Logik
- [x] **Phase 5:** Mistral Fusion-Prompt (Text + Audio)
- [x] **Phase 6:** Automatisches Enrollment + gleitender Mittelwert
- [x] **Phase 7:** Integration in transcription_tasks.py Pipeline
- [x] **Phase 8:** AssigneeResolver + Phonetic Matching (NEU)
- [x] **Phase 9:** Display Transcript + Temperature 0.1 (NEU)
- [x] **Phase 10:** Single Speaker Fallback reaktiviert (NEU)

---

## 8. Risiken & Gegenmaßnahmen

| Risiko | Gegenmaßnahme |
|---|---|
| ONNX-Modell nicht ladbar | Fallback auf Text-Inferenz |
| Audio zu kurz (< 5 Sek.) | Segmente concat oder SKIP |
| Cold Start (keine Profile) | Text-Inferenz als einzige Quelle |
| Cross-Tenant-Leakage | Strikte `client_id`-Filterung |
| Embedding-Drift | Gleitender Mittelwert, max. 20 Samples |
| Arabische Transliterationen | Double Metaphone phonetisches Matching |
| Mistral Halluzination | Display Transcript + Temperature 0.1 |
| Ambiguous Assignees | External assignment mit `is_ambiguous=True` |
