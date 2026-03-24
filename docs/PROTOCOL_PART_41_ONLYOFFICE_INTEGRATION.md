PROTOKOLL: PART_41_ONLYOFFICE_INTEGRATION

Datum: 24.03.2026
Status: Geplant
🎯 ZIEL

Einführung eines selbst gehosteten "OnlyOffice Document Servers" zur nahtlosen Online-Bearbeitung von generierten Meeting-Protokollen (.docx) direkt im Browser. Diese Lösung garantiert 100%ige Datensouveränität (ISO 27001), da die Dokumente die eigene Infrastruktur nicht verlassen.

🔧 TECHNOLOGIEN

    - OnlyOffice Document Server (Docker)
    - Python (FastAPI) für Callback-API und JWT-Signierung
    - React (Frontend) für die Editor-Integration
    - MinIO (S3) als Dokumentenspeicher

📝 GEPLANTE ARBEITSSCHRITTE

    1.  **Infrastruktur**: Erweiterung der `docker-compose.yml` um den `onlyoffice-documentserver` Container. Konfiguration von internem Netzwerk-Routing und JWT-Secrets.
    2.  **Backend (API)**:
        - `GET /api/v1/pv/{pv_id}/onlyoffice/config`: Erstellt die Konfiguration für das Frontend, signiert mit einem JWT, und liefert eine temporäre (presigned) Download-URL von MinIO.
        - `POST /api/v1/pv/callback`: Verarbeitet das Webhook-Ereignis von OnlyOffice (Status 2 = "Ready for saving"). Lädt das bearbeitete Dokument von der bereitgestellten OnlyOffice-URL herunter, speichert es in MinIO und erstellt einen neuen Snapshot in der `PVVersion` Tabelle (ISO 27001 Audit-Trail).
    3.  **Frontend (React)**:
        - Erstellung einer neuen Komponente `PVEditor` (oder eines Modals), die die OnlyOffice JavaScript-API (über `api.js`) einbindet.
        - Integration eines "Online bearbeiten"-Buttons in der Dokumenten-Ansicht (dort, wo bisher nur der PDF/Word-Download-Button war).

⚠️ HERAUSFORDERUNGEN & LÖSUNGEN

    - **Sicherheit & Authentifizierung**: OnlyOffice muss wissen, dass die Anfrage legitim ist.
      *Lösung*: Striktes JWT-Signing zwischen Backend, Frontend und OnlyOffice. Das JWT-Secret wird in `.env` gespeichert.
    - **Interne Kommunikation (Docker)**: OnlyOffice muss das Backend (Callback) und MinIO (Download-URL) erreichen können, oftmals scheitert dies an Docker-DNS-Auflösungen.
      *Lösung*: Setzen von `ALLOW_PRIVATE_IP_ADDRESS=true` in OnlyOffice und saubere Nutzung der Docker-internen Aliase (z.B. `http://backend:8000`).

🔗 ZUSAMMENHANG ZUM PROJEKT

    Dieses Feature hebt die Software auf Enterprise-Niveau, da Nutzer fehlerhafte KI-Protokolle (Mistral) direkt im Workflow korrigieren können, ohne Dateien herunter- und wieder hochladen zu müssen.

📊 ERWARTETES ERGEBNIS

    Nutzer klicken im Dashboard auf "Bearbeiten" und sehen eine vollständige Textverarbeitung (wie Microsoft Word) im Browser. Änderungen werden automatisch im Meeting Automation System versioniert gespeichert.
