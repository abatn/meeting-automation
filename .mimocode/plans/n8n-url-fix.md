# n8n Workflow URL Fix — Phase 74

## Problem

3 n8n Workflows verwenden den falschen Hostname `meeting-automation-backend-1:8000`:
- `transcription-completed` (BOlWu12gdUfABJWW) — 5 Fehler in Folge
- `pv-validated` (DAd2jClIdg6wJtfy) — 1 Fehler
- `daily-reminders` (GpER66AvYwapRNP4) — 1 Fehler

Richtiger Hostname: `backend.meeting-automation-staging.svc.cluster.local:8000`

## Betroffene Workflows

| Workflow | ID | Fehler | Falsche URL |
|----------|-----|--------|-------------|
| transcription-completed | BOlWu12gdUfABJWW | 5x ENOTFOUND | `meeting-automation-backend-1:8000` |
| pv-validated | DAd2jClIdg6wJtfy | 1x ENOTFOUND | `meeting-automation-backend-1:8000` |
| daily-reminders | GpER66AvYwapRNP4 | 1x ENOTFOUND | `meeting-automation-backend-1:8000` |

## Fix

URL in der n8n DB korrigieren:
```sql
UPDATE workflow_entity
SET nodes = replace(nodes::text, 'meeting-automation-backend-1:8000', 'backend.meeting-automation-staging.svc.cluster.local:8000')::jsonb
WHERE nodes::text LIKE '%meeting-automation-backend-1%';
```

Danach n8n neustarten.
