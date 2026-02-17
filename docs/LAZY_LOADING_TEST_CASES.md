# Lazy Loading Test Cases

This document outlines manual test cases to validate the eager loading implementation across various services.

## TESTFALL_ML01: Meeting-Service Eager Loading
------------------------------------------------
**Ziel:** Prüfen ob alle Meeting-Beziehungen korrekt geladen werden.

**Vorgehen:**
1. Meeting mit organizer, recordings, transcriptions, pvs, actions erstellen.
2. `meeting = await meeting_service.get_meeting_by_id(db, meeting_id)` aufrufen.
3. Prüfen: `meeting.organizer.name` (sollte keinen zusätzlichen DB-Call auslösen)
4. Prüfen: `len(meeting.recordings)` (sollte keinen zusätzlichen DB-Call auslösen)
5. Prüfen: `len(meeting.transcriptions)` (sollte keinen zusätzlichen DB-Call auslösen)
6. Prüfen: `meeting.pvs[0].content` (sollte keinen zusätzlichen DB-Call auslösen)
7. Prüfen: `meeting.actions[0].description` (sollte keinen zusätzlichen DB-Call auslösen)

**Erwartet:** Keine zusätzlichen DB-Queries nach initialem Load.

## TESTFALL_RL01: Recording-Service Eager Loading
------------------------------------------------
**Ziel:** Prüfen ob Recording-Beziehungen korrekt geladen werden.

**Vorgehen:**
1. Recording mit meeting und transcription erstellen.
2. `recording = await recording_service.get_recordings_by_meeting(db, meeting_id)` aufrufen.
3. Prüfen: `recording[0].meeting.title` (sollte keinen zusätzlichen DB-Call auslösen)
4. Prüfen: `recording[0].transcription.content` (sollte keinen zusätzlichen DB-Call auslösen)

**Erwartet:** Alle Beziehungen sind bereits geladen.

## TESTFALL_AL01: Action-Service Eager Loading
------------------------------------------------
**Ziel:** Prüfen ob Action-Beziehungen korrekt geladen werden.

**Vorgehen:**
1. Action mit assignee und meeting erstellen.
2. `actions = await action_service.get_actions_for_user(db, user_id)` aufrufen.
3. Prüfen: `actions[0].assignee.email` (sollte keinen zusätzlichen DB-Call auslösen)
4. Prüfen: `actions[0].meeting.title` (sollte keinen zusätzlichen DB-Call auslösen)

**Erwartet:** Keine N+1 Queries.

## TESTFALL_PL01: PV-Service Eager Loading
------------------------------------------------
**Ziel:** Prüfen ob PV-Beziehungen korrekt geladen werden.

**Vorgehen:**
1. PV mit meeting und validated_by erstellen.
2. `pv = await pv_service.get_pv_by_id(db, pv_id)` aufrufen.
3. Prüfen: `pv.meeting.title` (sollte keinen zusätzlichen DB-Call auslösen)
4. Prüfen: `pv.validated_by.name` (sollte keinen zusätzlichen DB-Call auslösen)

**Erwartet:** Alle Beziehungen eager geladen.