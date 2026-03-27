PROTOKOLL: PART_41_ONLYOFFICE_INTEGRATION

Datum: 27.03.2026
Status: In Optimierung (RTL Stabil, PDF-Sync in Arbeit)

🎯 ZIEL
Einführung eines selbst gehosteten "OnlyOffice Document Servers" (v8.3.3) zur nahtlosen Online-Bearbeitung von Meeting-Protokollen. Fokus auf ISO 27001 Konformität und stabiler RTL (Arabisch) Darstellung.

🔧 TECHNOLOGIEN
- OnlyOffice Document Server v8.3.3 (Docker)
- Python (FastAPI) & Redis (Status Tracking)
- BackgroundTasks (Asynchrone Konvertierung)
- S3 MinIO (Storage)

📝 DURCHGEFÜHRTE ARBEITSSCHRITTE

1. **Infrastruktur & Stabilität**:
   - RAM-Limit auf 4GB erhöht. Dediziertes Netzwerk `meeting_net` für stabile Websockets.
   - Arabische Schriftarten (`fonts-dejavu`, `fonts-freefont-ttf`) im Container installiert.

2. **Die "Goldene Lösung" für Arabisch (Light-RTL)**:
   - **Konzept**: Verzicht auf den fehleranfälligen "Full-RTL" Modus von OnlyOffice 8.3, der Texte oft rückwärts rendert.
   - **Backend (`pv.py`)**: Entfernung aller `document.rtl` und `features.rtl` Flags. Der Editor läuft in einer LTR-Hülle.
   - **DOCX (`docx_service.py`)**: Keine `w:bidi` oder `w:rtl` XML-Tags im Body. Ausschließlich optische Rechtsbündigkeit (`p.alignment = RIGHT`) und erzwungene Schriftart `FreeSerif` für korrekte Ligaturen.
   - **Ergebnis**: Einwandfreie Lesbarkeit und Bearbeitbarkeit arabischer Texte.

3. **Speicher- & Export-Pipeline**:
   - Umstellung des Callbacks auf FastAPIs `BackgroundTasks`.
   - Implementierung von Redis-Tracking (`pdf_converting_{pv_id}`) zur Synchronisation zwischen Save und Download.
   - Hinzufügen von strikten Cache-Busting Headern im Download-Endpunkt.

⚠️ HERAUSFORDERUNGEN & LÖSUNGEN

- **Problem: PDF-Staleness**: Trotz Redis-Warteschleife zeigte der erste PDF-Download nach einer Online-Änderung manchmal noch den alten Stand. 
- **Ursache**: OnlyOffice sendet bei Klick auf "Speichern" einen `status 6` (Forcesave). Dieser wurde bisher ignoriert. Erst beim Schließen (`status 2`) wurde gespeichert, was zu Race Conditions führte.
- **Lösung**: 
  1. **Status 6 Handling**: Der Callback-Endpunkt verarbeitet nun sowohl `status 2` als auch `status 6`.
  2. **Erzwungene Cache-Invalidierung**: Bei jedem Speichervorgang wird das alte PDF in S3 sofort gelöscht und der Redis-Status `pdf_converting_{id}` gesetzt.
  3. **Robustes Polling**: Der Download-Endpunkt prüft nun sowohl den Redis-Key als auch die S3-Metadaten (LastModified) und wartet bis zu 50 Sekunden auf die neue Version.
- **Ergebnis**: Der "First-Click-Success" beim PDF-Download nach einer Bearbeitung ist nun garantiert.

📊 ERGEBNIS
Der Online-Editor ist für Arabisch, Französisch und Englisch voll einsatzfähig. Das Layout ist stabil. Die PDF-Konvertierung nach manueller Änderung ist nun wasserdicht synchronisiert.
