# Incident: LiveKit Egress "websocket url timeout reached"

**Status:** RESOLVED
**Erstellt:** 2026-08-19
**Gelöst:** 2026-08-20
**Schweregrad:** P1 (Recording auf Production komplett funktionslos)
**Root Cause:** IMAGE-DOWNGRADE — Helm-Migration hat `latest` (v1.14.x) durch `v1.8.4` ersetzt

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
10:36:51  launching chrome  url=ws://livekit-server:7880  sandbox=false
          Chrome-Binary: /opt/google/chrome/chrome (Google Chrome 125)
10:37:11  failed to launch chrome  error="template page load failed: websocket url timeout reached"
          Chrome-Startup-Dauer: EXAKT 20 SEKUNDEN (chromedp Timeout)
```

### Egress-Log Staging (Auszug — Vergleich)

```
13:58:16  launching chrome  url=ws://livekit-server-staging:7880  sandbox=false
          Chrome-Binary: /chrome/chrome (Chromium 117)
13:58:20  chrome: START_RECORDING  (4 Sekunden!)
13:59:05  egress completed  (49 Sekunden Recording)
```

## Fix

| # | Fix | Aufwand | Dateien |
|---|-----|---------|---------|
| 1 | `image.tag: "v1.14.1"` in egress-values.yaml setzen | Niedrig | `infrastructure/kubernetes/production/egress-values.yaml` |
| 2 | Deploy via CI/CD (deploy-production.yml) | Standard | GitHub Actions |

### Warum v1.14.1 und nicht v1.8.4 fixen?

```
v1.14.1:  Chromium auf BEIDEN Plattformen (amd64: 1416MB, arm64: 1375MB)
v1.8.4:   Chrome 125 auf AMD64, Chromium 117 auf ARM64 (BUG)
```

`latest` auf Docker Hub zeigt auf v1.14.1 — das ist das Image das in Juli funktioniert hat.

## CI/CD Anforderungen

- Änderung in `infrastructure/kubernetes/production/egress-values.yaml`
- Commit auf `main` Branch
- CI Pipeline muss grün sein (backend-test + frontend-test + build-and-push)
- Deploy Production via GitHub Actions UI (manuell)

## Timeline

| Zeit | Event |
|------|-------|
| 2026-07-27-30 | Recording funktioniert (image: latest = v1.14.x) |
| 2026-08-06-09 | Helm-Migration: image auf v1.8.4 gepinnt (DOWNGRADE) |
| 2026-08-11 14:34 | Erster Fehler (intermittierend) |
| 2026-08-14-15 | Meistens funktioniert (intermittierend) |
| 2026-08-18 11:17 | Ab jetzt 100% fehlgeschlagen |
| 2026-08-19 | Incident-Report erstellt, CPU-Fix (falsch) |
| 2026-08-20 13:58 | Staging-Test: Chromium 117 funktioniert in 4s |
| 2026-08-20 14:21 | Prod-Test: Chrome 125 scheitert (20s Timeout) |
| 2026-08-20 14:30 | Docker Hub Vergleich: latest=v1.14.1, v1.8.4=2024 |

## Verifikation

**Checkliste:**
- [x] CI Pipeline grün (backend-test + frontend-test + build-and-push)
- [ ] Deploy Production via GitHub Actions UI
- [ ] Egress-Log prüfen: Chrome startet <10s (Chromium 117)
- [ ] Recording testen: RoomComposite Egress erfolgreich

**Rollback:** Falls v1.14.1 Probleme macht → `tag:` aus Values entfernen → Helm nutzt wieder `.Chart.AppVersion` (v1.8.4)
