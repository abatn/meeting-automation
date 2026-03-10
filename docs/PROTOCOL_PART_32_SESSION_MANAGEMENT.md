PROTOKOLL: PART_32_SESSION_MANAGEMENT

Datum: 09.03.2026
Status: Abgeschlossen
🎯 ZIEL
Implementierung des "Vor Go-Live" Meilensteins für erweitertes Session-Management und JWT-Härtung gemäß ISO 27001 Roadmap. Verhinderung von Token-Diebstahl durch Begrenzung der Lebensdauer und Erzwingung eines inaktivitätsbasierten Logouts.

🔧 TECHNOLOGIEN
- Python / FastAPI (JWT Konfiguration)
- React / Redux (Frontend Session State)
- DOM Events (Inaktivitäts-Tracking)

📝 DURCHGEFÜHRTE ARBEITSSCHRITTE
1. **JWT-Härtung**:
   - Die Variable `ACCESS_TOKEN_EXPIRE_MINUTES` im Backend (`core/config.py`) wurde von `1440` (24h) auf `30` (Minuten) reduziert. Dies minimiert das Zeitfenster für Replay-Attacken erheblich.
2. **Erweiterter Logout-Flow**:
   - Eine neue Thunk-Action `performLogout` wurde in `authActions.ts` eingeführt. Diese stellt sicher, dass vor der Löschung des lokalen Zustands das Backend via `/api/v1/auth/logout` aufgerufen wird, um den Token serverseitig in die Redis-Blacklist aufzunehmen.
3. **Auto-Timeout (Inaktivität)**:
   - Die Komponente `AutoLogout.tsx` wurde im Frontend erstellt.
   - Sie überwacht die Events `mousemove`, `keydown`, `wheel`, `click` und `touchstart`.
   - Bleibt eine Aktion für 15 Minuten (900.000 ms) aus, wird `performLogout` getriggert und der User auf `/login` weitergeleitet.
   - Die Komponente umschließt in `App.tsx` das gesamte Routing.

⚠️ HERAUSFORDERUNGEN & LÖSUNGEN
- **Ressourcenschonendes Event-Tracking**: Die Überwachung von `mousemove` kann die Performance beeinträchtigen. Die Nutzung von `useCallback` für die Reset-Funktion verhindert unnötige Re-Renders der Hauptapplikation.

🔗 ZUSAMMENHANG ZUM PROJEKT
Damit ist ein weiterer kritischer Sicherheitsaspekt der "Vor Go-Live" Phase abgehakt. Das System schützt sich nun aktiv gegen unbeaufsichtigte, geöffnete Bildschirme (Clear Desk Policy der ISO 27001).

📊 ERGEBNIS
Der automatische Logout bei Inaktivität funktioniert reibungslos. Access Tokens verfallen nach 30 Minuten, was das Backend zwingt, den Refresh-Token-Flow zu validieren, wodurch die Systemsicherheit signifikant erhöht wurde.
