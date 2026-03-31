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

### 7. Dashboard-Audit & Beseitigung von "Müll-Arbeit" (Refactoring)
- **Sanierung der Manager-Ansichten:**
  - `DashboardManager.tsx` & `DashboardDG.tsx` wurden grundlegend refactored, da sie zuvor nur oberflächliche Mock-Designs ohne funktionale Logik enthielten.
  - **Glassmorphism-Standard:** Einführung von echtem `backdropFilter: "blur(12px)"` und 16px Radien für alle KPI-Karten, identisch zum `DashboardParticipant`.
  - **i18n-Vollendung:** Restlose Entfernung aller hartcodierten englischen Strings (z.B. "Frequently Delayed Tasks", "AI Suggestion Analytics"). Alle Texte werden nun über den `t()`-Hook bezogen.
  - **Backend-Logik Integration:** Ersetzung der Mock-Listen durch echte Daten aus dem `ReportService`. Manager sehen nun verifiziert die Meetings ihres gesamten Teams (basierend auf der `manager_id` Verknüpfung).

### 8. Finale Meeting-Logik & Button-Garantie
- **Zwei-Button-Prinzip:** Geplante Meetings zeigen nun **immer** parallel den `Cancel` (Rot/Outline) und den `Start/Join` Button an. Kein Button verdrängt mehr den anderen.
- **Lokale Zeit-Synchronisation:** Integration der `dayjs` Plugins `utc` und `timezone`. Vergleiche erfolgen nun gegen die lokale Browserzeit via Unix-Timestamps, was Fehlberechnungen bei Zeitverschiebungen vollständig eliminiert.
- **Echtzeit-Validierung (Scheduling):**
  - **Pflichtfelder-Sperre:** Der "Create"-Button ist erst aktiv, wenn alle Pflichtfelder (Titel, Datum, Uhrzeit, Ort, Teilnehmer) ausgefüllt sind.
  - **Past-Date-Prevention:** Meetings in der Vergangenheit können nicht mehr erstellt werden. Der `DatePicker` blockiert vergangene Tage (`minDate`).
- **Intelligente Listen-Filterung:** 
  - Die Liste "Recent Meetings" im Meeting Planner zeigt alle laufenden und geplanten Meetings an, plus das letzte historische Event (cancelled/expired).
  - Im **Department Manager Dashboard** wurde die Liste "My Upcoming Meetings" gestrafft: Sie zeigt **ausschließlich** aktive (`in_progress`) und bevorstehende (`planned`) Meetings an. Abgelaufene oder abgesagte Termine werden hier vollständig ausgeblendet, um die operative Übersicht zu maximieren.
- **Optimierte Button-UX:**
  - **Blau ("Start Now"):** Für Meetings in ferner Zukunft.
  - **Grün pulsierend ("Join"):** Automatisches Signal 15 Minuten vor Startzeit.
  - **Grün ("Join"):** Für verspätete Meetings ("Late"), um eine positive Handlungsaufforderung zu geben (ersetzt die warnende rote Farbe).
  - **Auto-Refresh:** Die Liste aktualisiert sich alle 30 Sekunden automatisch, um den Status-Übergang (z.B. von Start Now zu Join) ohne Page-Reload anzuzeigen.
- **Strikte Ablauf-Regel:** Ein Meeting wird exakt nach Ablauf der geplanten Dauer (Start + Duration) als `expired` markiert. In diesem Zustand wird der Text durchgestrichen und es erscheint ausschließlich der funktionale `Delete`-Button zum Aufräumen.
- **API-Vollendung:** Implementierung des fehlenden `DELETE /api/v1/meetings/{id}` Endpunkts im Backend zur physischen Bereinigung von Meeting-Leichen (inkl. kaskadierender Löschung von Teilnehmern und Agenden).

### 9. Action Items Tracker & Rollenbasierte Sichtbarkeit (RBAC)
- **Professioneller Aufgaben-Kreislauf (RBAC):**
  - Implementierung einer strikten rollenbasierten Sichtbarkeit für den Endpunkt `/api/v1/actions/my-actions`.
  - **Participant:** Sieht ausschließlich Aufgaben, die ihm explizit per ID, E-Mail oder durch "Fuzzy Matching" seines Namens (für AI-Zuweisungen) zugeordnet wurden.
  - **Manager:** Sieht die eigenen Aufgaben sowie alle Aufgaben seiner direkten Team-Mitglieder (ausgewertet über die `manager_id` der Untergebenen).
  - **Director General (DG):** Vollständiger Überblick über alle Aufgaben des Mandanten (Tenant).
- **Intelligentes AI-Namens-Matching:** Das System spaltet nun Vor- und Nachnamen auf und führt eine tolerante Suche (`ILIKE`) in den `external_name` Feldern durch, um Zuweisungsfehler der KI (z.B. "Herr Batnini" vs. "Abdelkader Batnini") auszugleichen.
- **UI-Stabilität (Error Boundary Fix):**
  - Die `StatusBadge.tsx` Komponente wurde robuster programmiert. Unbekannte oder fehlerhaft formatierte Status-Strings aus der Datenbank führen nicht mehr zum Absturz der React-Tabelle (`TypeError: can't access property "label"`). Es greifen nun saubere neutrale Fallbacks (z.B. "Unknown").
  - Alle Datenbank-Enums (`ActionStatus`) wurden auf konsistente Großschreibung (`PENDING`, `COMPLETED`) normiert.

### 10. Datenbank-Sanierung & Hierarchie-Tests
- **Korrektur der Testdaten (Users/Roles):** 
  - Die Benutzer `batniniabdelkader@yahoo.com` und `mohamedlarbi.nakti@gmail.com` wurden in der Tabelle `user_roles` manuell von der Rolle "Manager" auf "Participant" zurückgestuft, um den strikten RBAC-Filter realitätsnah zu testen.
  - Dem Account `manager@meeting.tn` wurde in der `users`-Tabelle die Führung über diese Participants (via `manager_id`) zugewiesen. Dies stellte sicher, dass die "Team-Sichtbarkeit" im Department Manager Dashboard korrekt greift.
- **Enum-Harmonisierung:** Manuelle SQL-Updates zur Konvertierung aller Kleinschrift-Status (z.B. 'pending') in der `actions`-Tabelle in den neuen Großschrift-Standard ('PENDING'), um `InvalidTextRepresentationError` Abstürze im Dashboard zu vermeiden.

### 11. Rollenbasierte Navigations-Differenzierung (RBAC Sidebar)
Um die Benutzererfahrung zu optimieren und die Datensicherheit (ISO 27001) zu erhöhen, wird die Sidebar-Navigation nun feingranular an die Benutzerrolle innerhalb des Kunden-Tenants angepasst:
- **Director General (DG):** Vollständiger Zugriff auf alle operativen und administrativen Unternehmensebenen. Sichtbare Menüpunkte: Dashboard, Meetings, Archive, Actions, Reports, Team und Billing.
- **Department Manager:** Fokus auf operative Steuerung und Team-Produktivität. Sichtbare Menüpunkte: Dashboard, Meetings, Archive, Actions, Reports und Team.
- **Participant:** Maximaler Fokus auf die eigene Arbeit. Sichtbare Menüpunkte: Dashboard, Meetings, Archive und Actions (Eingeschränkte Sicht). Reports, Team und Billing sind für diese Rolle ausgeblendet.

## 📊 ERGEBNIS
Die Applikation wirkt nun wie aus einem Guss. Durch die Beseitigung der funktionalen Defizite ("Müll-Arbeit") in den Dashboards, die strikte RBAC-Filterung im Action Tracker und die Stabilisierung der Zeit-Logik im Meeting Planner ist das System nun bereit für den produktiven Einsatz in verschiedenen Hierarchieebenen. Die technische Performance der Pipeline wurde via Log-Analyse bestätigt.
