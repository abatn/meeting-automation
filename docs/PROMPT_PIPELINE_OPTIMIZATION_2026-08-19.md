# Prompt: Pipeline-Optimierung — LiveKit Recording Pipeline

## AUFGABE

Du bist ein erfahrener DevOps-Ingenieur und Python-Performance-Experte. Analysiere die folgende LiveKit Recording Pipeline und erarbeite eine professionelle Optimierungsstrategie, um die Gesamtdauer von 117s auf ≤90s zu reduzieren.

## KONTEXT

**System:** Meeting-Automation SaaS (FastAPI + Celery + PostgreSQL)
**Pipeline:** LiveKit Recording → S3 → Gladia Transcription → Speaker ID → ONNX Reassignment → Sentinel LLM → Mistral PV → Persistence
**Hardware:** Staging: ARM64 (4 Cores, 23GB RAM) | Production: AMD64 (8 Cores, 24GB RAM)
**Ziel:** ≤90s end-to-end (Recording Start → PV gespeichert)

## IST-ZUSTAND (Live-Daten vom 19.08.2026, Staging)

```
Phase                  Dauer     Status
─────────────────────  ────────  ──────
S3 Download            0.02s     ✅ Gut
Gladia Transcription   6.09s     ✅ Gut
ONNX Init              0.43s     ✅ Gut
Speaker ID             30.09s    ⚠️ LANGSAM
ONNX Reassignment      21.71s    ⚠️ LANGSAM
Sentinel LLM           52.12s    ⚠️ LANGSAM
Mistral PV             6.10s     ✅ Gut
Persistence            0.11s     ✅ Gut
─────────────────────  ────────  ──────
GESAMT                 116.98s   ⚠️ 2 Min (Ziel: ≤90s)
```

**Einsparpotenzial:** -79s (Speaker ID -25s, ONNX Reassignment -17s, Sentinel LLM -37s)

## CODEBASE-REFERENZ

| Datei | Zweck |
|-------|-------|
| `backend/app/tasks/transcription_tasks.py` | Hauptpipeline (Zeilen 1-1000+) |
| `backend/app/services/assignee_resolver.py` | Speaker ID / Assignee Resolution |
| `backend/app/services/phonetic_matcher.py` | Double Metaphone für arabische Namen |
| `backend/app/services/pv_service.py` | Mistral PV Generation |
| `backend/app/services/sentinel_service.py` | Sentinel LLM (Qwen2.5-1.5B GGUF) |
| `docs/PIPELINE_QUICK_WINS.md` | Bekannte Optimierungsmöglichkeiten |
| `docs/LIVEKIT_ROUTE_PIPELINE_2026-06-07.md` | Pipeline-Architektur |

## DEINE AUFGABEN

### 1. Speaker ID Phase (30.09s → Ziel: ~5s)

**Untersuche:**
- Warum dauert Speaker ID 30s für nur 1 Speaker mit conf=1.00?
- Gibt es unnötige Schritte (phonetic matching, fuzzy matching) wenn conf bereits 1.00 ist?
- Kann die ONNX-Inferenz parallelisiert werden (aktuell sequenziell pro Segment)?
- Gibt es ein Caching-Möglichkeit für ONNX-Embeddings?

**Erwarte:**
- Konkrete Code-Stellen mit Zeilennummern
- Geschätzte Einsparung pro Optimierung
- Risiko-Bewertung ( Accuracy vs. Speed)

### 2. ONNX Reassignment Phase (21.71s → Ziel: ~5s)

**Untersuche:**
- Warum 21.71s für 0/9 Reassignments (nichts wurde reassignet)?
- Wird ONNX Reassignment überhaupt ausgeführt wenn Speaker ID bereits 100% confidence hat?
- Gibt es eine Skip-Logik wenn `reassigned=0`?
- Kann die Phase komplett übersprungen werden wenn Speaker ID erfolgreich war?

**Erwarte:**
- Skip-Logik Vorschlag (wann ist Reassignment nötig?)
- Geschätzte Einsparung

### 3. Sentinel LLM Phase (52.12s → Ziel: ~15s)

**Untersuche:**
- Warum 52s für nur 1 Chunk (263 Zeichen)?
- Ist das Modell (Qwen2.5-1.5B GGUF) auf ARM64 optimiert?
- Gibt es Quantisierungs-Optionen (GGUF Q4/Q5) die Speed erhöhen?
- Kann das Modell vorgeladen werden (Pre-warming) statt pro Task zu laden?
- Gibt es eine Lightere Alternative (z.B. Qwen2.5-0.5B)?

**Erwarte:**
- Modell-Vergleich (Speed vs. Quality)
- Quantisierungs-Empfehlung
- Pre-warming Vorschlag

### 4. Gesamt-Optimierung

**Erwarte:**
- Priorisierte Maßnahmenliste (Quick Wins zuerst)
- Geschätzte Gesamtdauer nach Optimierung
- Risiko-Bewertung (Accuracy vs. Speed vs. Aufwand)
- Implementierungs-Reihenfolge

## VERBOTE

- NICHTS modifizieren (kein Code, kein Git, kein kubectl)
- Nur lesen und analysieren
- Keine Spekulationen — nur faktenbasierte Empfehlungen

## ANTWORT-FORMAT

```
## Zusammenfassung
[2-3 Sätze Gesamtbewertung]

## Phase 1: Speaker ID
### Analyse
[Was ist der Grund für die 30s?]
### Optimierungsvorschläge
[1. Vorschlag mit Code-Stelle + geschätzte Einsparung]
[2. Vorschlag mit Code-Stelle + geschätzte Einsparung]

## Phase 2: ONNX Reassignment
### Analyse
[Warum 21.71s für 0/9 Reassignments?]
### Optimierungsvorschläge
[Skip-Logik + geschätzte Einsparung]

## Phase 3: Sentinel LLM
### Analyse
[Warum 52s für 1 Chunk?]
### Optimierungsvorschläge
[Modell-Alternative + Quantisierung + Pre-warming]

## Gesamt-Optimierung
### Priorisierte Maßnahmen
[1. Quick Win: X (Einsparung: Ys)]
[2. Quick Win: X (Einsparung: Ys)]
[3. Medium: X (Einsparung: Ys)]

### Erwartetes Ergebnis
Vorher: 117s → Nachher: ~Xs (Ziel: ≤90s)

### Risiko-Bewertung
[Accuracy-Einbußen? Komplexität?]
```
