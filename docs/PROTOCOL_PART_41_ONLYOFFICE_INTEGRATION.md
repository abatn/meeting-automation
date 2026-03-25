PROTOKOLL: PART_41_ONLYOFFICE_INTEGRATION

Datum: 24.03.2026
Status: Abgeschlossen
🎯 ZIEL

Einführung eines selbst gehosteten "OnlyOffice Document Servers" zur nahtlosen Online-Bearbeitung von generierten Meeting-Protokollen (.docx) direkt im Browser. Diese Lösung garantiert 100%ige Datensouveränität (ISO 27001), da die Dokumente die eigene Infrastruktur nicht verlassen.

🔧 TECHNOLOGIEN

    - OnlyOffice Document Server (Docker)
    - Python (FastAPI) für Callback-API und JWT-Signierung
    - React (Frontend) für die Editor-Integration
    - MinIO (S3) als Dokumentenspeicher
    - python-docx für komplexe XML-Manipulationen (RTL)

📝 DURCHGEFÜHRTE ARBEITSSCHRITTE

    1. **Infrastruktur & Docker**: Integration des `onlyoffice` Containers in die `docker-compose.yml`. Setzen der JWT-Tokens und `ALLOW_PRIVATE_IP_ADDRESS=true` für Docker-interne Kommunikation.
    2. **Backend API (`pv.py`)**: 
        - Implementierung von `/onlyoffice/config` zur Token-Generierung.
        - Implementierung des Callbacks (`/onlyoffice/callback`), der Status `2` (Speichern) verarbeitet, die DOCX-Datei von OnlyOffice lädt, sie in S3 speichert und **automatisch eine PDF-Konvertierung anstößt**.
        - Anpassung der Download-Endpunkte, um stets bevorzugt die in S3 manuell bearbeiteten Versionen (DOCX & PDF) mit intelligenter Retry-Logik auszuliefern.
    3. **RTL-Support (`docx_service.py`)**: Tiefe Manipulation der Word-XML-Struktur (Einsetzen von `<w:bidi/>` auf Absatzebene und `<w:rtl/>` / `<w:cs val="Arial"/>` auf Run-Ebene), um sicherzustellen, dass Arabisch in OnlyOffice mit korrekter Satzzeichen-Positionierung (Right-to-Left) gerendert wird.
    4. **Frontend Integration (`OnlyOfficePage.tsx`)**: Schaffung einer dedizierten Route `/editor/:pvId`, die den Editor im Vollbild öffnet. Umstellung der "Online bearbeiten"-Buttons auf echte `<a href="...">` Links, um sicherzustellen, dass sich der Editor browserübergreifend (Chrome, Firefox, Safari) in einem neuen Tab öffnet und das Dashboard im ursprünglichen Tab intakt bleibt.

⚠️ HERAUSFORDERUNGEN & LÖSUNGEN

    - **RTL (Right-to-Left) Rendering in OnlyOffice**: Einfaches Setzen der Textausrichtung reichte nicht für arabische Zeichen. 
      *Lösung*: Chirurgische Anpassung des XML-Codes mittels `python-docx` (`OxmlElement('w:bidi')`), um das gesamte Dokument und jeden Run explizit als Complex Script auszuweisen.
    - **Race Condition beim PDF Download**: Nutzer klickten auf "Download", bevor OnlyOffice die Konvertierung abgeschlossen hatte.
      *Lösung*: Implementierung einer Retry-Logik (max. 3 Versuche mit 2 Sekunden Wartezeit), falls eine bearbeitete DOCX-Datei in S3 existiert, das PDF aber noch fehlt.
    - **SaaS-Datenmodell (client_id Bug)**: Das `PVVersionModel` stürzte beim Speichern ab (`TypeError: 'client_id' is an invalid keyword argument`), da das Modell in der DB die Client-ID nur implizit über das Eltern-PV hält.
      *Lösung*: Parameter im Code entfernt.
    - **OnlyOffice ConvertService JSON-Error**: Der Endpunkt `.ashx` lieferte XML zurück, was zu Fehlern beim Parsen führte.
      *Lösung*: Umstellung auf den modernen `/converter` Endpunkt und Setzen des Headers `Accept: application/json`.
    - **Frontend "Neuer Tab" Blockade (Firefox)**: React Router `Link` mit `target="_blank"` wurde von Firefox teils im selben Tab verarbeitet.
      *Lösung*: Umstellung auf echte `href`-Links mit zusätzlichem `onClick={window.open}` Fallback und `e.preventDefault()`, um das Event korrekt an den Browser zu übergeben.

🔗 ZUSAMMENHANG ZUM PROJEKT

    Dieses Feature hebt die Software auf Enterprise-Niveau, da Nutzer fehlerhafte KI-Protokolle (Mistral) direkt im Workflow korrigieren können, ohne Dateien herunter- und wieder hochladen zu müssen.

📊 ERGEBNIS

    Das System erlaubt nun eine reibungslose, ISO-27001-konforme Online-Bearbeitung von Meetings in drei Sprachen (AR, EN, FR) in einem nativen neuen Tab, wobei Änderungen automatisch versioniert und on-the-fly in PDFs überführt werden.
