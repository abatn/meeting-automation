# False Alarms — Security Audit 2026-06-05

**Datum**: 2026-06-05
**Kontext**: ISO 27001 Security Audit, Phase 1 Remediation

---

## Finding #3: Soft-deleted Users (False Alarm)

**Status**: FALSE ALARM
**Begründung**: Die Analyse zeigte, dass `User.deleted_at` als potenzielle Data-Leakage-Vektor identifiziert wurde. Weitere Analyse bestätigte, dass `team_service.py:318-319` beim Soft-Delete NICHT nur `deleted_at` setzt, sondern auch `user.status = UserStatus.DISABLED.value`. Die Authentifizierung in `deps.py:162` prüft `user.status != UserStatus.ACTIVE.value` — gelöschte Benutzer sind DISABLED und scheitern am Status-Check. Die `deleted_at`-Spalte ist redundant für die Auth-Blockierung, dient aber der ISO 27001-konformen Audit-Trail-Erhaltung.

**Keine Änderung nötig.**

---

## Finding #7: `ensure_future` Race Condition (False Alarm)

**Status**: FALSE ALARM
**Begründung**: Die Analyse zeigte, dass `asyncio.ensure_future()` in `transcription_tasks.py:891` als potenzielle Race Condition identifiziert wurde (Fire & Forget, Exception geht verloren). Weitere Analyse bestätigte, dass Celery Worker den **prefork pool** verwenden (nicht eventlet/gevent). In prefork-Workers gibt es keinen laufenden Event-Loop. `asyncio.get_event_loop()` gibt eine neue, nicht-laufende Schleife zurück. `loop.is_running()` gibt immer `False` zurück → `run_until_complete()` wird immer ausgeführt. Der `ensure_future`-Pfad ist toter Code und wird nie erreicht.

**Keine Änderung nötig.**

---

## Zusammenfassung

| Finding | Kategorie | Status | Aktion |
|---------|-----------|--------|--------|
| #3 Soft-deleted Users | Data Leakage | FALSE ALARM | Keine Änderung nötig |
| #7 ensure_future Race | Concurrency | FALSE ALARM | Keine Änderung nötig |
