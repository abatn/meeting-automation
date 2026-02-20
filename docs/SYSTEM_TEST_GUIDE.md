# 🧪 System-Test & Validierungs-Anleitung

Diese Anleitung führt dich in ca. 15 Minuten durch die Validierung des gesamten **Meeting Automation Systems**.

---

## 1. Container-Status prüfen
Stelle sicher, dass die gesamte Infrastruktur bereit ist.

**Befehl:**
```bash
docker compose ps
```

**Erwartete Ausgabe:**
Alle Container sollten den Status `Up (healthy)` oder `Up` haben.
- `postgres`, `redis`, `rabbitmq`, `minio`, `n8n`, `backend`, `frontend`, `celery-worker`, `celery-beat`.

**Fehlersuche:**
- Falls ein Container `Exit 1` anzeigt: `docker compose logs [service_name]`
- Falls Ports belegt sind: `netstat -tulpn | grep [PORT]`

---

## 2. Backend API validieren
Testet die Kern-Logik und Konnektivität.

### A. Health-Check
**Befehl:**
```bash
curl -X GET http://localhost:8000/health
```
**✅ Erfolg:** `{"status": "healthy", "version": "1.0.0"}`

### B. JWT Auth & Login
**Befehl:**
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "username=admin@example.com&password=admin_password"
```
**✅ Erfolg:** Erhalt eines `access_token` und `refresh_token`.

---

## 3. Frontend Zugriff & UI
Prüfung der Benutzeroberfläche und Lokalisierung.

1. **URL:** Öffne [http://localhost:3000](http://localhost:3000)
2. **Login:** Nutze die Credentials (z.B. `admin@example.com`).
3. **Dashboards:** Navigiere zwischen DG Dashboard, Manager und Participant.
   - *Check:* Werden die Recharts-Grafiken korrekt gerendert?
4. **RTL Test:** Schalte die Sprache auf Arabisch (`ar-TN`).
   - *Check:* Spiegelt sich das Layout (`dir="rtl"`)? Ist die Sidebar auf der rechten Seite?

---

## 4. n8n & Workflow Automation
Validierung der Integrations-Engine.

1. **UI:** Öffne [http://localhost:5678](http://localhost:5678) (User: `admin`, PW: `admin_password`).
2. **Workflows:** Überprüfe unter "Workflows", ob folgende aktiv/vorhanden sind:
   - `meeting-created`, `audio-uploaded`, `pv-validated`.
3. **Webhook Check:** Führe `curl http://localhost:5678/healthz` aus.

---

## 5. Minio S3 Storage
Test der Datei-Infrastruktur.

1. **Console:** Öffne [http://localhost:9001](http://localhost:9001) (User: `minio_user`, PW: `minio_password`).
2. **Buckets:** Prüfe, ob der Bucket `meeting-recordings` existiert.
3. **Upload Test:** Lade manuell eine kleine `.wav` Datei hoch.

---

## 6. Integrationstest (Happy Path)
Der vollständige Durchlauf des Systems.

1. **Schritt 1:** Erstelle im Frontend ein neues Meeting.
2. **Schritt 2:** Lade eine Audio-Datei im `MeetingPlanner` hoch.
3. **Schritt 3 (Backend):** Prüfe Logs: `docker compose logs -f celery-worker`.
   - Suche nach: `Task app.tasks.transcription_tasks.process_audio[ID] received`.
4. **Schritt 4 (n8n):** Prüfe in n8n unter "Executions", ob der Workflow getriggert wurde.
5. **Schritt 5 (Output):** Nach ca. 2-5 Min. sollte das transkribierte PV im `TranscriptionViewer` erscheinen.
6. **Schritt 6 (WhatsApp):** Falls konfiguriert, prüfe die WhatsApp API Logs auf ausgehende Nachrichten.

---

## 7. Troubleshooting & Ports

### Wichtige Ports:
| Service | Port |
| :--- | :--- |
| Frontend | 3000 |
| Backend API | 8000 |
| n8n | 5678 |
| Minio Console | 9001 |
| RabbitMQ Management | 15672 |

### Log-Analyse:
- **Echtzeit-Monitoring:** `docker compose logs -f [service_name]`
- **Kombinierte Logs:** `docker compose logs --tail=100 -f backend celery-worker`

---

## ✅ "Es funktioniert!" - Kriterien
- [ ] Alle Container sind `healthy`.
- [ ] Login im Frontend ist erfolgreich.
- [ ] Hochgeladene Audio-Dateien erscheinen im Minio-Bucket.
- [ ] n8n Executions zeigen keine Fehler ("Success").
- [ ] Das generierte PV enthält extrahierte "Action Items".