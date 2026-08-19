# Incident: LiveKit Egress "websocket url timeout reached"

**Status:** IN PROGRESS
**Erstellt:** 2026-08-19
**Schweregrad:** P1 (Recording auf Production komplett funktionslos)
**Root Cause:** CPU-Starvation (Egress 1 Core, Chrome braucht >1 Core)

---

## Zusammenfassung

LiveKit Egress auf Production schlägt bei jedem Recording mit dem Fehler `template page load failed: websocket url timeout reached` fehl. Auf Staging funktioniert alles.

**Der Fehler ist KEIN WebSocket-Fehler** — es ist ein **Chrome-Start-Timeout** aus chromedp (20s Limit). Chrome kann bei 1 CPU und Production-Last nicht rechtzeitig starten.

## Vergleich: Staging vs Production

| Eigenschaft | Staging | Production |
|-------------|---------|------------|
| **CPU Cores** | 4 | 8 |
| **RAM** | 23 GB | 24 GB |
| **Architektur** | ARM64 (aarch64) | AMD64 (x86_64) |
| **Node Load** | 24% (~1 CPU) | 34% (~2.7 CPU) |
| **Egress CPU Limit** | 1 Core | 1 Core |
| **Chromium Version** | 117.0.5874.0 | 117.0.5874.0 (identisch) |
| **"not enough cpu" Error** | ✅ JA | ✅ JA (gleicher Fehler!) |
| **"high cpu usage" WARN** | ❌ NEIN | ✅ JA (load: 1.2-2.8) |
| **Chrome-Startup** | <20s ✅ | >20s ❌ (Timeout) |
| **Recording** | ✅ Funktioniert | ❌ Fehlschlägt |

## Root Cause

**CPU-Starvation auf Production:** Egress CPU-Limit = 1 Core. Chrome + Xvfb + GStreamer brauchen >1 Core. Bei Production-Node-Last (34%) startet Chrome nicht innerhalb des 20s chromedp Timeouts.

### Beweiskette

1. **Egress-Log (BEIDE Cluster):** `ERROR: not enough cpu for some egress types, minimumCpu: 2, available: 1`
2. **NUR Production:** `WARN: high cpu usage` (load: 1.2-2.8) → Chrome kann CPU nicht nutzen
3. **Staging:** Keine high-cpu Warnungen → Chrome startet <20s → Recording funktioniert
4. **Chrome-Startup auf Production:** EXAKT 20s (12:24:33 → 12:24:53) = chromedp Timeout
5. **chromedp Quellcode:** `wsURLReadTimeout = 20s`
6. **GitHub Issue livekit/egress#578:** "This is actually a chrome startup timeout"

### Egress-Log Production (Auszug)

```
12:11:18  ERROR: not enough cpu for some egress types
          minimumCpu: 2, recommended: 3, available: 1
12:11:18  cpu available: 1.000000 max cost: 2.000000
12:24:33  launching chrome (URL: http://localhost:7980/?...)
12:24:37  WARN: high cpu usage (load: 1.21)
12:24:39  WARN: high cpu usage (load: 1.15)
12:24:53  FAILED: template page load failed: websocket url timeout reached
          Chrome-Startup-Dauer: EXAKT 20 SEKUNDEN (chromedp Timeout)
```

## Empfohlene Fixes

| # | Fix | Aufwand | Dateien |
|---|-----|---------|---------|
| 1 | Egress CPU-Limit von 1 auf 2 erhöhen | Niedrig | `egress-values.yaml` (Prod) |
| 2 | `cpu_cost.room_composite_cpu_cost` auf 2.0 setzen | Niedrig | `egress-values.yaml` (Prod) |
| 3 | Deploy via CI/CD (deploy-production.yml) | Standard | GitHub Actions |

## CI/CD Anforderungen

- Änderung in `infrastructure/kubernetes/production/egress-values.yaml`
- Commit auf `main` Branch
- CI Pipeline muss grün sein (backend-test + frontend-test + build-and-push)
- Deploy Production via GitHub Actions UI (manuell)
- Kein SSH zu Production ohne Genehmigung

## Timeline

| Zeit | Event |
|------|-------|
| 2026-08-19 12:24 | Test 1522 fehlgeschlagen (websocket timeout) |
| 2026-08-19 12:24 | Egress-Log: Chrome-Startup 20s (Timeout) |
| 2026-08-19 14:00 | Unabhängige Analyse durchgeführt |
| 2026-08-19 14:30 | Root Cause identifiziert: CPU-Starvation |
| 2026-08-19 15:30 | Incident-Report erstellt |
| 2026-08-19 16:00 | Fix implementiert (CPU limit 1→2) |
| 2026-08-19 16:05 | Git Push → CI Pipeline gestartet |
| 2026-08-19 TBD | Deploy Production via GitHub Actions |
| 2026-08-19 TBD | Verifikation: Recording auf Production testen |

## Verifikation

Nach Deploy: Recording auf Production testen und prüfen ob `websocket url timeout`不再 auftritt.

**Checkliste:**
- [ ] CI Pipeline grün (backend-test + frontend-test + build-and-push)
- [ ] Deploy Production via GitHub Actions UI
- [ ] Egress-Log prüfen: Kein `ERROR: not enough cpu` mehr
- [ ] Egress-Log prüfen: Chrome startet <10s (statt 20s Timeout)
- [ ] Recording testen: RoomComposite Egress erfolgreich
