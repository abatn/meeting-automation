# PROTOKOLL: PART 42 - DASHBOARD & MEETING ROOM UI REDESIGN ("Linear/Stripe"-Stil)

**Datum:** 28.03.2026
**Status:** Abgeschlossen ✅
**Ziel:** Vollständiges visuelles Redesign der inneren Applikations-Komponenten (Dashboard, Meeting Planner, Meeting Room, Navigation), um sie an den "Modern Enterprise"-Standard der Landing Page anzugleichen.

## 🎯 ZIEL
Beseitigung klobiger Schatten und überdimensionierter Schriften zugunsten eines flachen, kompakten und funktionalen Designs. Strikte i18n-Implementierung ohne Hardcoded-English-Fallbacks.

## 📝 DURCHGEFÜHRTE ARBEITSSCHRITTE

### 1. Globale Navigation & Shell
- **Sidebar:** Bereinigt auf operative Kernpunkte (Dashboard, Meetings, Actions, Reports). Entfernung administrativer Punkte zur Steigerung der Fokus-Qualität.
- **Navbar:** Implementierung eines Profil-Hubs oben rechts. Umzug von `Team`, `Billing` und `Security` in ein elegantes Dropdown-Menü beim Usernamen.
- **Branding:** Konsistente Nutzung von `appNamePart1/2` für das Logo.

### 2. Live Meeting Assistant (MeetingRoom.tsx)
- **2-Spalten-Architektur:** 
    - Links: Status-Zentrum mit hochpräzisem Timer, Meeting-ID und Audio-Controls.
    - Rechts: Validierungs-Workflow mit synchron scrollbaren Karten für Transkription und AI-Draft.
- **Workflow-Optimierung:** 
    - "Edit Online" Button mit automatischer `pvId`-Abfrage (Polling) zur nahtlosen OnlyOffice-Anbindung.
    - Export-Optionen (PDF) direkt in der Dokumenten-Toolbar neben der Sprachwahl positioniert.
    - Der "Approve & Sign" Button löst nun den korrekten Endpunkt `/validate` für den n8n-Webhook aus und ist durch Doppelklick-Schutz (`isApproving`) gesichert.
- **Visuelles Feedback:** Pulsierender "LIVE"-Badge und rote Record-Indikatoren.

### 3. Meeting Planner (MeetingPlanner.tsx)
- **Struktur:** 7/5 Grid-Layout. Links kompaktes Planungs-Formular mit gruppierten Zeit/Datum-Feldern. Rechts dynamische und dichte Liste der letzten Meetings und Kultur-Kalender.
- **Design:** Flache Outline-Karten, `borderRadius: 3`, keine Elevation.
- **Smart Navigation:** 
    - Automatische Erkennung, ob ein Meeting in `<= 15 Minuten` startet (Sprung in den Live Room) oder in der Zukunft liegt (Formular-Reset mit Bestätigung).
- **Intelligente Meeting-Liste (Recent Meetings):**
    - Filtern von abgesagten (`cancelled`) Meetings aus der Schnellauswahl.
    - Dringlichkeits-Sortierung: `in_progress` > `planned` (nach Nähe) > `completed`.
    - Phasengesteuerte Buttons: Geplante Meetings zeigen `Start Now` und `Cancel`. Der `Join Room` Button wird erst 15 Minuten vor Start leuchtend grün. Überfällige Meetings wechseln auf den Status `late`. Abgelaufene Meetings (`expired`) werden durchgestrichen und zeigen nur noch `Delete`.
- **Soft Cancel:** Implementierung eines neuen Backend-Endpunkts `PATCH /api/v1/meetings/{id}/cancel` zur Statusänderung (ISO 27001 Audit-Trail) ohne Hard Delete.
- **Logik-Restaurierung:** 
    - Die asynchrone Live-Suche im Team-Directory (`teamApi.searchTeam`) bei der Teilnehmer-Auswahl wurde wiederhergestellt.
    - Der *Tunisian Cultural Calendar* (Feiertags-Sperre und Warnungen) wurde in das neue flache Design integriert.

### 4. Action Tracker & Berichte
- **Tracker:** Kompakte Tabelle mit `12px` Header (uppercase) und `14px` Inhalten. Subtile Hover-Effekte und eckige Action-Buttons (`borderRadius: 2`).
- **Berichte:** Ersetzung von Paper-Komponenten durch strukturierte Box-Container mit feinen Rahmen.

### 5. Internationalisierung (i18n) & Korrekturen
- **Harmonisierung:** Alle 3 JSON-Dateien (EN, FR, AR) auf exakt gleiche Struktur gebracht.
- **Eliminierung von "Müll":** Entfernung aller hartgecodeten englischen Strings und Fallbacks aus dem JSX-Code. Korrektur von Tippfehlern in der arabischen Übersetzung. Hinzufügen von Status-Schlüsseln (`late`, `overdue`, `expired`, `cancelled`, `completed`).
- **RTL-Support:** Validierung der Layout-Spiegelung für das gesamte Dashboard.


### 6. Protocol Archive & Intelligent AI Search (Library)
- **Neues Modul `MeetingArchive.tsx`:** Eine dedizierte Seite für das Durchsuchen vergangener Meetings, zugänglich über die Sidebar ("Bibliothèque" / "الأرشيف").
- **AI Tagging (Backend):**
  - Erweiterung des `PV`-Modells und der Datenbank (`pvs` Tabelle) um ein unverschlüsseltes `tags`-Feld.
  - Der Mistral-Prompt im `PVService` wurde so modifiziert, dass er automatisch 3-5 thematische Schlagworte aus dem Protokoll extrahiert.
  - Die Tags werden vom Celery-Worker gespeichert und über das Schema `MeetingWithPV` (ohne Lazy-Loading-Fehler) an das Frontend geliefert.
- **Smart Filter UI:**
  - Die Archiv-Tabelle bietet Filter für Datum, Raum und "AI Topics".
  - **Datensouveränität (ISO 27001):** Die Suche nach "Themen" filtert über die unverschlüsselten Mistral-Tags, während der eigentliche Protokollinhalt verschlüsselt bleibt.
- **i18n & Datumsformatierung:**
  - Ersatz von nativen HTML-Datumsfeldern durch den **MUI DatePicker** (`@mui/x-date-pickers`).
  - Strikte Koppelung des `AdapterDayjs` an die aktive Sprache (`i18n.language`), sodass Kalender-Popups, Wochentage und Platzhalter (z.B. `JJ/MM/AAAA` für FR, arabische Formate für AR) vollautomatisch und nativ gerendert werden.

### 7. Personal & Department Manager Dashboards (Mobile & RTL Optimierung)
- **Modern Enterprise Transformation:**
  - Komplette Überarbeitung von `DashboardParticipant` und den Manager-Ansichten auf den "Glassmorphism"-Standard (transparente Hintergründe, Blur-Effekte, 16px Border-Radius).
  - Ersetzung klobiger Standard-MUI-Schatten durch flache, subtile Rahmen (`border: 1px solid rgba(0,0,0,0.05)`).
- **RTL (Arabisch) & Mobile-First Fixes:**
  - **Sidebar "Double-Flip" Fix:** Korrektur des MUI-Drawer Anchors auf `anchor={i18n.dir() === 'rtl' ? 'right' : 'left'}`. Entfernung von manuellen `isRtl`-Hacks, um Konflikte mit dem `stylis-plugin-rtl` zu vermeiden. Die mobile Sidebar fährt nun im arabischen Modus sauber von rechts ein.
  - **Logische CSS-Properties:** Ersatz von harten physischen Werten (`borderRight`, `paddingRight`, `marginLeft`) durch logische Eigenschaften (`borderInlineEnd`, `paddingInlineEnd`), um ein perfektes Spiegeln in RTL-Sprachen zu garantieren.
  - **Mobile Table Rescue:** Entfernung von `overflow: "hidden"` auf Wrapper-Elementen und Einführung von zwingendem `overflowX: "auto"` für `TableContainer` in *Action Tracker*, *Meeting Archive* und *Analytical Reports*. Dies verhindert das Abschneiden von Tabellen auf Smartphones und ermöglicht sauberes horizontales Scrollen im RTL-Modus, ohne die Tabelle zu stauchen.
  - **Smart Hover & Touch UX:** Die Hover-Animationen in den Dashboards (`translateX`) respektieren nun die Leserichtung (`isRtl ? '-4px' : '4px'`). Die Touch-Targets (Padding `py: 1.5 - 2`) wurden für Smartphones vergrößert.
- **Typografie-Upgrade:**
  - Harmonisierung der Typografie: Sicherstellung, dass arabischer Text nicht gequetscht wird (angepasste `lineHeight` und `minWidth` für Icons).

## 📊 ERGEBNIS
Die Applikation wirkt nun wie aus einem Guss. Vom ersten Besuch der Landing Page bis zur Bearbeitung eines Protokolls im Meeting Room herrscht eine konsistente, hochprofessionelle Design-Sprache. Die technische Performance der Pipeline wurde via Log-Analyse bestätigt.
