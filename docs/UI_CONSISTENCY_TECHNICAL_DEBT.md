# UI-Konsistenz – borderRadius & boxShadow Vereinheitlichung

## Status

- **Typ:** Technical Debt
- **Bereich:** Frontend Dashboard UI
- **UI-Basis:** Material UI (MUI) mit eigenem Theme
- **Priorität:** Nach Pipeline-Stabilisierung
- **Geschätzter Aufwand:** 1 Tag für alle 7 Dashboard-Seiten

---

## Ist-Zustand

Das globale MUI-Theme definiert aktuell nur teilweise einheitliche Formwerte:

| Komponente | Globaler Theme-Wert |
|---|---:|
| Paper / Cards | `12` |
| Button | `8` |
| Chip | nicht global definiert |
| OutlinedInput | nicht global definiert |
| Select | nicht global definiert |
| Avatar | nicht global definiert |

Mehrere Dashboard-Seiten überschreiben diese globalen Werte lokal über `sx`, inline Styles oder lokale Style-Objekte.

---

## Lokale Abweichungen nach Dashboard-Seite

| Seite | Lokale `borderRadius`-Werte | Lokale `boxShadow`-Werte | Abweichung vom globalen Theme |
|---|---|---|---|
| **MeetingRoom** | Paper/Cards häufig `3`; Buttons häufig `2`; weitere Box-/Card-Werte wie `2.5`, `1.5`; Avatar mit eigenem Shadow-State | Explizite Shadows z. B. `0 1px 3px rgba(0,0,0,0.04)`, `0 1px 2px rgba(...)`, `0 2px 8px rgba(...)`, Avatar-Ring | Ja |
| **Meetings** | Paper via `glassStyle` mit `24px`; Create-Button `12px`; Action-Buttons teils `8px`; Chip `6px`; Box `12px` | Keine expliziten Shadows | Ja |
| **Library** | Filter-Paper `3`; TableContainer-Paper `3`; View-Button `1.5`; TextField/Select/DatePicker `2`; Chip `1` | TableContainer `boxShadow: "none"` | Ja |
| **Action Items** | Toolbar-Paper `3`; TableContainer-Paper `3`; Buttons `2`; TextField Input `2`; Chip `1.5`; IconButtons `2` | Keine expliziten Shadows | Ja |
| **Analytical Reports** | Box-Wrapper `3`; ProductivityTable-Paper `12px`; Scrollbar-Thumb `3px` | Keine expliziten Shadows | Teilweise |
| **Team Management** | Keine lokalen `borderRadius`-Overrides auf Page- oder Child-Page-Ebene | Keine lokalen `boxShadow`-Overrides | Nein |
| **Subscription & Billing** | Current-Plan-Paper `3`; Plan-Cards `3`; TableContainer `3`; Usage-Box `3`; Upgrade-Buttons `2` | Keine expliziten Shadows; `elevation={0}` | Ja |

---

## Problem

Das globale Theme wird lokal überschrieben:

- Globales `MuiPaper.borderRadius = 12` wird auf mehreren Seiten durch lokale Werte ersetzt.
- Globales `MuiButton.borderRadius = 8` wird auf mehreren Seiten durch lokale Werte ersetzt.
- Chip-, Input-, Select- und Avatar-Formen sind nicht global vereinheitlicht.
- `boxShadow` wird teils lokal gesetzt, teils entfernt, teils über `elevation={0}` ersetzt.
- Dadurch entstehen visuell unterschiedliche Card-, Button-, Input- und Badge-Formen innerhalb desselben Dashboards.

---

## Ausnahme

**Team Management** folgt aktuell dem globalen Theme:

- Keine lokalen `borderRadius`-Overrides für Paper/Cards.
- Keine lokalen `borderRadius`-Overrides für Buttons.
- Keine lokalen `boxShadow`-Overrides.
- Buttons nutzen den globalen Button-Wert.
- Paper/TableContainer nutzen keine lokalen Formabweichungen.

---

## Zielbild

HeroUI-ähnliche Formkonsistenz:

| Komponente | Zielwert |
|---|---:|
| Cards / Paper | `12` |
| Buttons | `8` |
| Chips | `20` |
| Inputs / OutlinedInput / Select | `30` |
| Avatare | `40px` mit Ring |

---

## Scope

Betroffene Dashboard-Seiten:

1. MeetingRoom
2. Meetings
3. Library
4. Action Items
5. Analytical Reports
6. Team Management
7. Subscription & Billing

---

## Priorisierung

- **Priorität:** Nach Pipeline-Stabilisierung
- **Grund:** Die UI-Konsistenz ist eine Design-/Technical-Debt-Aufgabe, während Recording → Transcription → PV → Actions aktuell die höhere Produktstabilität hat.

---

# Duplicate Actions Bug

## Status

- **Typ:** Bug / Technical Debt
- **Bereich:** Backend Pipeline — Action-Erstellung
- **Priorität:** Nach Pipeline-Stabilisierung
- **Geschätzter Aufwand:** 0.5 Tag

---

## Symptom

Meeting `fce9c026` hat **25 Actions aber nur 5 unique Titel**:

```
"Test the program's stamping functionality"     → 11×
"Perform trial runs on program modifications"   → 5×
"Finalize the meeting transcript"               → 3×
"Finaliser et rédiger le procès-verbal..."      → 1×
"Superviser le test du programme..."            → 1×
```

Alle wurden innerhalb von 6 Minuten (00:08–00:14) erstellt. Es gibt **nur 1 Recording** für dieses Meeting.

---

## Wurzelanalyse

### Bug 1: Kein Pipeline-Guard

`_process_recording_pipeline` (transcription_tasks.py:139) prüft NICHT ob:
- Recording bereits `completed` oder `transcribing` ist
- Ein anderer Pipeline-Lauf bereits läuft
- Kein Redis-Lock auf Recording-ID

### Bug 2: Mehrere Entry-Points

`process_recording.delay()` kann aus 4 unabhängigen Pfaden aufgerufen werden:

| Pfad | Datei | Zeile |
|------|-------|-------|
| LiveKit Webhook `egress_ended` | `livekit.py` | 389 |
| Direkt-Upload | `recording_service.py` | 83 |
| Stop-Stream | `recording_service.py` | 194 |
| Manueller Trigger | `transcriptions.py` | 36 |

Kein Koordinationsmechanismus zwischen diesen Pfaden.

### Bug 3: Keine Action-Dedup in `_save_pv_and_actions`

`_save_pv_and_actions` (transcription_tasks.py:989-1012) erstellt neue `Action`-Rows OHNE zu prüfen ob:
- Für dieses Meeting bereits Actions mit gleichem Titel existieren
- Für dieses Recording bereits Actions erstellt wurden

PV-Idempotenz existiert (Zeile 906-917) — aber NUR für PV, nicht für Actions.

### Contributing Factors

| Faktor | Auswirkung |
|--------|------------|
| `task_acks_late=True` | Crashed Tasks werden erneut ausgeführt |
| `autoretry_for=(Exception,)` | Jeder Fehler löst automatischen Retry aus (max 3×) |
| Redis Webhook-Dedup ist fail-open | Bei Redis-Ausfällen kommen doppelte Webhooks durch |
| `stop_stream()` + Webhook | Beide können für dasselbe Recording feuern |

---

## DB-Beweis

```sql
-- 25 Actions, 5 unique Titel
SELECT meeting_id, COUNT(*) as action_count, COUNT(DISTINCT title) as unique_titles
FROM actions GROUP BY meeting_id ORDER BY action_count DESC;

-- Nur 1 Recording für dieses Meeting
SELECT id, status, meeting_id FROM recordings
WHERE meeting_id = 'fce9c026-f586-4386-b7a4-c6f5cbb19500';
-- → 1 row, status=completed
```

---

## Lösungsansätze

### Fix 1: Action-Dedup in `_save_pv_and_actions` (Minimal)

Vor der Action-Erstellung (Zeile 989) prüfen:
```python
existing = await db.execute(
    select(Action.title).where(
        Action.meeting_id == recording.meeting_id,
        Action.client_id == recording.client_id,
    )
)
existing_titles = {row[0] for row in existing}
```
Nur Actions erstellen, deren Titel nicht bereits existiert.

### Fix 2: Pipeline-Status-Guard (Empfohlen)

Am Eingang von `_process_recording_pipeline` (nach Zeile 149):
```python
if recording.status in ("completed", "transcribing"):
    logger.info(f"Recording {recording_id} already {recording.status}, skipping.")
    return
```

### Fix 3: Redis-Lock (Optional)

Vor dem Start des Pipelines einen Redis-Lock auf `recording:{recording_id}` setzen mit TTL = `task_time_limit` (600s). Verhindert parallele Pipeline-Läufe für dasselbe Recording.

---

## Priorisierung

- **Priorität:** Nach Pipeline-Stabilisierung
- **Grund:** Die Duplizierung ist ein Backend-Bug, der die Datenqualität betrifft, aber die Kernfunktionalität nicht blockiert. Bevor behoben wird, sollte die Pipeline stabil laufen (ONNX-Embedding-Extraktion, `_concatenate_segments` finally-Bug).
