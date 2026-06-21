# Meeting Status Enum Fix — Documentation

## Problem
Meeting Room (`/meetings/live/:id`) war im Frontend nicht sichtbar. "Join Room" Button wurde nicht angezeigt.

## Root Cause
SQLAlchemy's `SQLEnum(MeetingStatus)` speicherte standardmäßig den Enum-**Namen** (`PLANNED` uppercase) statt den Enum-**Wert** (`planned` lowercase) in PostgreSQL.

| Ebene | Wert (vor Fix) | Wert (nach Fix) |
|-------|----------------|-----------------|
| PostgreSQL Enum Type | `PLANNED, IN_PROGRESS, COMPLETED, CANCELLED` | `planned, in_progress, completed, cancelled` |
| DB Data | `PLANNED` | `planned` |
| SQLAlchemy ORM | `MeetingStatus.PLANNED.value = "planned"` | `MeetingStatus.PLANNED.value = "planned"` |
| FastAPI Response | `"PLANNED"` | `"planned"` |
| Frontend Vergleich | `m.status === 'planned'` → **false** | `m.status === 'planned'` → **true** |

## Changes Made

### Schritt 1: Frontend — Case-Insensitive Vergleiche
**Dateien:**
- `frontend/src/components/meetings/MeetingPlanner.tsx`
- `frontend/src/components/reports/DashboardManager.tsx`

**Änderungen:**
```diff
- m.status === 'planned'
+ m.status?.toLowerCase() === 'planned'

- m.status === 'in_progress'
+ m.status?.toLowerCase() === 'in_progress'
```

**E2E-Verifikation:** ✅ `npm run build` erfolgreich, dist/ in Container kopiert

### Schritt 2: Backend — SQLEnum values_callable
**Datei:** `backend/app/models/meeting.py`

**Änderung:**
```diff
  status: Mapped[MeetingStatus] = mapped_column(
-     SQLEnum(MeetingStatus), default=MeetingStatus.PLANNED
+     SQLEnum(MeetingStatus, values_callable=lambda x: [e.value for e in x]), default=MeetingStatus.PLANNED
  )
```

**E2E-Verifikation:** ✅ `MeetingStatus.PLANNED.value = "planned"` bestätigt

### Schritt 3: DB-Migration — Enum-Werte konvertieren
**SQL:**
```sql
-- Neue lowercase values hinzufügen
ALTER TYPE meetingstatus ADD VALUE 'planned';
ALTER TYPE meetingstatus ADD VALUE 'in_progress';
ALTER TYPE meetingstatus ADD VALUE 'completed';
ALTER TYPE meetingstatus ADD VALUE 'cancelled';

-- Bestehende Daten konvertieren
UPDATE meetings SET status = 'planned' WHERE status = 'PLANNED';
UPDATE meetings SET status = 'in_progress' WHERE status = 'IN_PROGRESS';
UPDATE meetings SET status = 'completed' WHERE status = 'COMPLETED';
UPDATE meetings SET status = 'cancelled' WHERE status = 'CANCELLED';
```

**Ergebnis:** 8 Meetings von `PLANNED` → `planned` konvertiert

**E2E-Verifikation:** ✅ `SELECT status, COUNT(*) FROM meetings GROUP BY status;` → `planned | 8`

### Schritt 4: Deploy
- Backend container neugestartet
- Celery worker neugestartet
- Frontend dist/ in nginx container kopiert

**E2E-Verifikation:** ✅
- Backend health: `{"status":"healthy","version":"1.0.0"}`
- Celery worker: `celery@6305c0689d07 ready.`
- ORM Test: `m.status.value = "planned"`, `m.status == MeetingStatus.PLANNED = True`
- FastAPI jsonable_encoder: `status = "planned"`

## Verification Summary

| Schritt | Test | Ergebnis |
|---------|------|----------|
| 1. Frontend fix | `npm run build` | ✅ Success |
| 2. Backend enum | `MeetingStatus.PLANNED.value` | ✅ `"planned"` |
| 3. DB migration | `SELECT status FROM meetings` | ✅ `planned` (8 rows) |
| 4. Deploy | Backend health + Celery ready | ✅ Healthy |
| 5. API serialization | `jsonable_encoder(status)` | ✅ `"planned"` |

## Files Changed
- `frontend/src/components/meetings/MeetingPlanner.tsx` (2 lines)
- `frontend/src/components/reports/DashboardManager.tsx` (2 lines)
- `backend/app/models/meeting.py` (1 line)
- PostgreSQL `meetingstatus` enum type (4 new values added, data migrated)

## Date
2026-06-02

---

## 🔧 FIX: Pipeline Status-Transition (21.06.2026)

### Problem
Meeting-Status wurde im Recording-Pipeline nie von `"planned"` auf `"completed"` aktualisiert. `recording.status` wurde gesetzt, aber `meeting.status` blieb permanent auf `"planned"`.

### Lösung
`transcription_tasks.py:263` — Nach `recording.status = "completed"` wird jetzt auch `meeting.status = "completed"` gesetzt.

### Datei geändert
- `backend/app/tasks/transcription_tasks.py` (6 Zeilen)

### Zusammenfassung aller Fixes
| Fix | Datei | Problem |
|-----|-------|---------|
| Enum lowercase | `meeting.py` | SQLAlchemy speicherte Uppercase |
| Frontend case-insensitive | `MeetingPlanner.tsx`, `DashboardManager.tsx` | Vergleiche waren case-sensitive |
| **Pipeline transition** | `transcription_tasks.py` | **meeting.status wurde nie auf completed gesetzt** |
