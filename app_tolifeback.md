# Emergency Recovery Workflow: Bringing the App Back to Life

**Datum:** 26.03.2026
**Szenario:** Kritischer Systemausfall nach fehlerhafter Analytics-Implementierung (ImportErrors, Zirkelbezüge, Datenbank-Inkonsistenzen).
**Ziel:** Wiederherstellung des stabilen SaaS-Multi-Tenant-Zustands (Stand Part 36/41).

---

## 🛠️ Schritt-für-Schritt Rekonstruktion

### 1. Code-Bereinigung (Purge)
Zuerst wurden alle fehlerhaften Dateien und unvollständigen Code-Fragmente aus dem Dateisystem entfernt, um die Python-Import-Pipeline zu heilen.
*   **Aktion:** `git checkout .` und `git clean -fd`.
*   **Manuelle Löschung:** Entfernen von Resten in `backend/app/api/v1/analytics.py` und den zugehörigen Services.

### 2. Infrastruktur-Reset
Löschen aller persistenten Daten-Volumes, um eine "Clean Slate" (saubere Basis) in der Datenbank zu erzwingen.
*   **Befehl:** `docker compose down -v`
*   **Effekt:** Alle inkonsistenten PostgreSQL-Tabellen und S3-Fragmente wurden physisch gelöscht.

### 3. Kern-Infrastruktur Boot
Start der Basis-Dienste ohne die Anwendungslogik, um die Datenbank-Erreichbarkeit sicherzustellen.
*   **Befehl:** `docker compose up -d postgres redis minio rabbitmq onlyoffice`
*   **Infrastruktur-Härtung (OnlyOffice Fonts):** Um professionelles Rendering (insb. Arabisch) sicherzustellen:
    ```bash
    docker exec -u 0 meeting-automation-onlyoffice-1 bash -c "apt-get update && apt-get install -y fonts-dejavu fonts-freefont-ttf fonts-noto-core fonts-noto-extra && /usr/bin/documentserver-generate-allfonts.sh"
    ```

### 4. Datenbank-Rettung (The "Alembic Fix")
**Problem:** Die Migration `4fb76575fee0` stürzte ab, weil die Spalte `language` in `action_suggestions` fehlte.
**Lösung:** Manueller SQL-Eingriff im laufenden Container via Python-Einzeiler (SQLAlchemy):
*   **Eingriff:** 
    ```bash
    docker compose run --rm backend bash -c "alembic upgrade 0ec3faaa42b1 && python -c 'import sqlalchemy; ... conn.execute(\"ALTER TABLE action_suggestions ADD COLUMN IF NOT EXISTS language VARCHAR DEFAULT '\''en'\'';\"); ...' && alembic upgrade head"
    ```
*   **Ergebnis:** Die Migrations-Pipeline wurde repariert und auf `head` gebracht.

### 5. Daten-Initialisierung (Seeding)
Wiederherstellung der SaaS-Mandantenstruktur und der Test-Benutzer.
*   **Aktion:** Ausführung von `seed_plans.py` (Subscription-Modelle) und `seed_users.py` (DG, Manager, Participant Rollen).

### 6. Full Application Boot
Hochfahren der restlichen Dienste, sobald das Fundament stabil war.
*   **Befehl:** `docker compose up -d backend frontend celery-worker celery-beat n8n`

### 7. Finaler System-Check & Orchestrierung
Nutzung des zentralen Setup-Skripts für die n8n-Integration und S3-Bucket Validierung.
*   **Befehl:** `./setup-system.sh`

---

## ✅ Verifizierung des Erfolgs
Das System gilt als "wiederbelebt", wenn:
1.  **Backend-Logs:** `Application startup complete` ohne Tracebacks anzeigen.
2.  **Login:** Der Zugriff mit `admin@meeting.tn` / `Password123!` erfolgreich ist.
3.  **Mandanten-Check:** Die `client_id` im JWT-Token korrekt gesetzt ist.
4.  **Editor-Check:** OnlyOffice via `/editor/:id` geladen werden kann.

---
**Wichtiger Hinweis:** Dieser Workflow ist nur für den Notfall-Reset in der Entwicklungsumgebung gedacht. In Produktion müssen Schema-Korrekturen zwingend über saubere Alembic-Down-Revisions erfolgen.
