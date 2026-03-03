PROTOKOLL: PART_19_AUDIT_PHASE_1_2_FIXES

Datum: 27.02.2026
Status: Abgeschlossen
🎯 ZIEL

Behebung der in Phase 1 und Phase 2 des 100% System-Audits gefundenen kritischen Fehler im Bereich asynchrone Task-Verarbeitung (Celery) und Dokumentation der Sprechererkennung (Diarization) nach der AI-Transition.

🔧 TECHNOLOGIEN

- Python (asyncio, Celery)
- FastAPI (Backend Tasks)

📝 DURCHGEFÜHRTE ARBEITSSCHRITTE

1. **Celery Worker Absturz-Behebung (Phase 2):**
   - **Problem:** Der Task `app.tasks.email_tasks.send_daily_reminders` führte zu `NotRegistered` Fehlern, was den Celery-Worker zum Absturz brachte (Exit 255). Außerdem waren Celery-Tasks mit `async def` deklariert, was Celery nativ nicht unterstützt.
   - **Lösung:** 
     - In `backend/app/tasks/email_tasks.py` wurden die Tasks `send_reminder_via_n8n` und `daily_reminder_task` so umgeschrieben, dass sie als synchrone Celery-Wrapper fungieren (`def`), in denen manuell eine asyncio-Event-Loop initialisiert wird (`loop.run_until_complete`), um die asynchronen Backend-Services sicher aufzurufen.
     - In `backend/app/tasks/celery_app.py` wurde der Beat-Schedule korrigiert, sodass er nun auf `daily_reminder_task` verweist, anstatt auf das nicht existierende `app.tasks.email_tasks.send_daily_reminders`.

2. **Diarization Ghost-Service Analyse (Phase 1):**
   - **Problem:** Der Diarization-Service (`diarization_service.py`) verwendet `pyannote.audio` für die lokale Sprechererkennung. Durch die "AI Transition" (Entfernung schwerer ML-Container) wurden diese Abhängigkeiten in `requirements.txt` entfernt.
   - **Lösung/Status:** Die Sprechererkennung wirft aktuell einen abgefangenen `ImportError` und gibt bei jeder Transkription eine leere Sprecherliste zurück. Whisper fängt dies als Fallback auf und ordnet den gesamten Text einem Single-Speaker zu. Das System crasht also nicht mehr. Für das aktuelle Setup wurde dieser Zustand als gewünscht/stabil akzeptiert, da die Transkriptions-Pipeline so robust durchlaufen kann, ohne durch OOM (Out of Memory) Kills abzustürzen.

3. **Backend API Serialisierungs-Bug / Test-Fixes:**
   - **Problem:** Die Unit-Tests (`test_create_meeting`) schlugen mit einem `MissingGreenlet` Fehler fehl. Dies lag daran, dass FastAPI versuchte, Lazy-Loading Felder (`participants`, `agendas`) eines SQLAlchemy-Models asynchron zu serialisieren, nachdem ein `await db.refresh(meeting)` aufgerufen wurde.
   - **Lösung:** In `backend/app/api/v1/meetings.py` wurden die Endpunkte für Create und Update so umgeschrieben, dass sie die SQLAlchemy-Instanz stattdessen über einen expliziten `selectinload` Query neu aus der Datenbank laden, bevor sie das Model an Pydantic zurückgeben. Die Tests (`test_meetings.py`) sind nun grün.

⚠️ HERAUSFORDERUNGEN & LÖSUNGEN

- **Asyncio in Celery:** Celery 5.x hat nach wie vor Probleme mit nativen `async def` Tasks. Der Workaround mit `asyncio.new_event_loop()` verhindert, dass der Worker aufgrund von "Event loop is closed" crasht.
- **Sprechererkennung (Diarization):** Ohne lokale ML-Bibliotheken ist eine saubere Sprechererkennung aktuell nicht verfügbar. Falls dies ein kritisches Feature wird, muss künftig auf eine externe API (z.B. AssemblyAI oder ein Deepgram Wrapper) umgestellt werden, anstatt Pyannote lokal zu laden.

🔗 ZUSAMMENHANG ZUM PROJEKT

Diese Fehlerbehebungen stabilisieren den kritischen Pfad der Meeting-Verarbeitung und der n8n-Erinnerungen. Der "Silent Fail" bei Erinnerungen und die Celery-Worker-Abstürze sind damit behoben.

📊 ERGEBNIS

✅ Celery-Beat und Celery-Worker können nun stabil starten, ohne an asynchronen Tasks oder falsch registrierten Cron-Jobs zu scheitern.
✅ Die Diarization-Falle führt nicht mehr zu System-Crashes.
