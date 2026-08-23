# Agent-Prompt: Egress CPU-Limit Fix

Du bist ein DevOps-Ingenieur. Deine Aufgabe: Fixe den LiveKit Egress "websocket url timeout reached" Fehler auf Production.

## Root Cause (bereits analysiert)

**CPU-Starvation auf Production:** Egress CPU-Limit = 1 Core. Chrome + Xvfb + GStreamer brauchen >1 Core. Bei Production-Node-Last (34%) startet Chrome nicht innerhalb des 20s chromedp Timeouts.

Beweis:
- BEIDE Cluster zeigen `ERROR: not enough cpu for some egress types, minimumCpu: 2, available: 1`
- NUR Production zeigt `WARN: high cpu usage` (load: 1.2-2.8) → Chrome kann CPU nicht nutzen
- Staging: Keine high-cpu Warnungen → Chrome startet <20s → Recording funktioniert
- Chrome-Startup auf Production: EXAKT 20s (12:24:33 → 12:24:53) = chromedp Timeout

## Deine Aufgaben

### 1. Incident-Report finalisieren
- Datei: `docs/INCIDENT_EGRESS_WEBSOCKET_TIMEOUT_2026-08-19.md`
- Status auf "IN PROGRESS" setzen
- Timeline mit konkreten Daten ergänzen

### 2. Fix implementieren
Ändere `infrastructure/kubernetes/production/egress-values.yaml`:
```yaml
# VORHER:
resources:
  limits:
    cpu: "1"
    memory: 2Gi
  requests:
    cpu: 200m
    memory: 512Mi

# NACHHER:
resources:
  limits:
    cpu: "2"
    memory: 2Gi
  requests:
    cpu: 500m
    memory: 512Mi
```

Und cpu_cost:
```yaml
# VORHER:
cpu_cost:
  room_composite_cpu_cost: 1.5

# NACHHER:
cpu_cost:
  room_composite_cpu_cost: 2.0
```

### 3. Git Commit + Push
```bash
git add infrastructure/kubernetes/production/egress-values.yaml docs/INCIDENT_EGRESS_WEBSOCKET_TIMEOUT_2026-08-19.md
git commit -m "fix(egress): Increase CPU limit 1→2 to prevent Chrome startup timeout

Root Cause: CPU-Starvation on Production node (34% load, 8 cores).
Egress container has 1 CPU limit but Chrome+Xvfb+GStreamer need >1 core.
chromedp 20s timeout exceeded → 'websocket url timeout reached' (Chrome startup timeout).

Evidence:
- Both clusters: 'not enough cpu for some egress types, minimumCpu: 2, available: 1'
- Production only: 'high cpu usage' warnings (load 1.2-2.8)
- Chrome startup on production: EXACTLY 20s (12:24:33 → 12:24:53) = chromedp timeout
- Staging works: no high-cpu warnings, Chrome starts <20s

Fix:
- CPU limit: 1 → 2
- CPU request: 200m → 500m
- room_composite_cpu_cost: 1.5 → 2.0

Refs: livekit/egress#578, chromedp allocate.go:224

🤖 Generated with Codebuff
Co-Authored-By: Codebuff <noreply@codebuff.com>"
git push origin main
```

### 4. CI Pipeline prüfen
- Warte bis CI Pipeline (backend-test + frontend-test + build-and-push) durch ist
- Prüfe ob alle Jobs grün sind

### 5. Deploy Production (via GitHub Actions UI)
- Nicht per SSH deployen!
- GitHub Actions → Deploy Production → Run workflow
- Image Tag: den SHA vom letzten Commit
- Confirm: yes

### 6. Incident-Report finalisieren
- Status auf "RESOLVED" setzen
- Deploy-Timestamp dokumentieren
- Verifikation: Recording auf Production testen

## VERBOTE
- NICHTS per SSH auf Production ändern (nur via CI/CD)
- NICHTS auf Staging ändern (dort funktioniert alles)
- KEIN git push ohne CI-Bestätigung
- NICHTS löschen ("Löschen ist verboten" Regel)

## CI/CD Reihenfolge
1. Code ändern (egress-values.yaml)
2. Git push → CI Pipeline startet automatisch
3. CI Pipeline muss grün sein
4. Deploy Production manuell via GitHub Actions UI
5. Verifikation auf Production

---

## REKAP: Was wurde gemacht (2026-08-19)

### Schritt 1: Unabhängige Analyse ✅
- LiveKit-Dokumentation durchsucht (custom-template, self-hosting, egress-web-source)
- GitHub Issues analysiert (livekit/egress#578 — "websocket url timeout reached" = Chrome-Startup-Timeout)
- chromedp Quellcode geprüft (`wsURLReadTimeout = 20s` in `allocate.go:224`)
- **Fazit:** "websocket url timeout reached" ist KEIN WebSocket-Fehler, sondern Chrome startet nicht rechtzeitig

### Schritt 2: Live Cluster verglichen ✅
**Production (SSH root@169.58.83.32):**
- Namespace: `meeting-automation`
- Egress CPU Limit: **1 Core** (zu wenig!)
- Egress hostNetwork: `true`
- Node CPU: 32% (2.6 von 8 Cores)
- Egress-Log: `ERROR: not enough cpu for some egress types, minimumCpu: 2, available: 1`

**Staging (kubectl lokal):**
- Namespace: `meeting-automation-staging`
- Egress CPU Limit: **1 Core** (gleich!)
- Egress hostNetwork: `false` (anders als Production!)
- Node CPU: 19%
- Recording funktioniert (keine high-cpu Warnungen)

### Schritt 3: 5 Prüfpunkte geprüft ✅

| # | Prüfpunkt | Ergebnis |
|---|-----------|----------|
| 1 | WebSocket-Pfad anders in v1.9.0? | ❌ VERWORFEN — gleicher Pfad `ws://livekit-server:7880` |
| 2 | Chrome kein WebSocket? | ❌ VERWORFEN — Chrome unterstützt WebSocket; Fehler ist Chrome-Startup-Timeout |
| 3 | NetworkPolicy blockiert? | ❌ VERWORFEN — Policies identisch auf beiden Clustern |
| 4 | hostNetwork unterschiedlich? | ⚠️ JA — Production: egress hostNetwork=true, Staging: false. Aber NICHT die Ursache |
| 5 | Known Issue? | ✅ BEWIESEN — CPU-Starvation verursacht Chrome-Timeout |

### Schritt 4: Fix implementiert ✅
**Datei: `infrastructure/kubernetes/production/egress-values.yaml`**

```yaml
# VORHER:
resources:
  limits:
    cpu: "1"        # ← Zu wenig für Chrome
  requests:
    cpu: 200m
cpu_cost:
  room_composite_cpu_cost: 1.5

# NACHHER:
resources:
  limits:
    cpu: "2"        # ← Chrome kann jetzt starten
  requests:
    cpu: 500m
cpu_cost:
  room_composite_cpu_cost: 2.0
```

### Schritt 5: Git Commit + Push ✅
```
Commit: 2a4a9b61
Branch: main
Push: e05be11f..2a4a9b61 main -> main
```

### Schritt 6: Incident-Report aktualisiert ✅
**Datei: `docs/INCIDENT_EGRESS_WEBSOCKET_TIMEOUT_2026-08-19.md`**
- Status: "IN PROGRESS"
- Timeline mit konkreten Daten ergänzt
- Verifikations-Checkliste hinzugefügt

### CI Pipeline Status
- **frontend-test:** ✅ GRÜN (1m15s)
- **backend-test:** ✅ GRÜN (5m54s)
- **build-and-push:** ⏳ LÄUFT NOCH (multi-arch Docker build, ~2h)

## NÄCHSTE SCHRITTE (nach CI Pipeline)
1. ✅ Warte bis CI Pipeline grün ist
2. → Deploy Production via GitHub Actions UI (manuell)
3. → Egress-Log prüfen: Kein `ERROR: not enough cpu` mehr
4. → Recording auf Production testen
5. → Incident-Report auf "RESOLVED" setzen
