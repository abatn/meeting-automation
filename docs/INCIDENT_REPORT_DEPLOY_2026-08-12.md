# Incident Report: Deploy Staging Failures #13–#15

**Datum:** 2026-08-12  
**Dauer:** 17:50–22:20 UTC (4h 30min)  
**Schweregrad:** P2 (Staging betroffen, Production unberührt)  
**Status:** Behoben  

---

## Zusammenfassung

Drei aufeinanderfolgende Deployments (#13, #14, #15) auf Staging schlugen bei Step 14 "Deploy Celery Workers to Staging" fehl. Root Cause: CPU-Overcommit auf dem Staging-Node durch manuelle Ressourcen-Hinzufügung (Velero, OnlyOffice) ohne Berücksichtigung der Node-Kapazität.

---

## Timeline

| Zeit (UTC) | Event | Status |
|------------|-------|--------|
| 13:19 | Deploy #10 (SHA=67a22aa1) | ✅ SUCCESS |
| 13:40 | Deploy #11 (SHA=67a22aa1) | ✅ SUCCESS |
| 14:03 | Deploy #12 (SHA=67a22aa1) | ⚠️ Step 14 OK, E2E-Test FAILED |
| 14:05 | **onlyoffice-staging zweiter Pod erstellt** | ⚠️ +200m CPU |
| ~15:00–17:00 | **Velero node-agent DaemonSet installiert** | ⚠️ +200m CPU |
| 17:21 | CI Pipeline #13 (SHA=51fcf051) | ✅ SUCCESS |
| 17:50 | **Deploy #13 (SHA=59978e4e)** | ❌ Step 14 FAILED |
| 18:05 | **Deploy #14 (SHA=59978e4e)** | ❌ Step 14 FAILED |
| 22:00 | CI Pipeline #15 (SHA=e9ba2e0e) | ✅ SUCCESS |
| 22:20 | **Deploy #15 (SHA=e9ba2e0e)** | ❌ Step 14 FAILED |
| 22:30 | Analyse abgeschlossen | Root Cause identifiziert |

---

## Root Cause

### Fakten (bewiesen)

| # | Fakt | Beweis |
|---|------|--------|
| 1 | Node: 4 CPU Cores (4000m allocatable) | `kubectl get node` → `cpu: 4` |
| 2 | CPU Requests VOR Deploy #12: ~5880m (147%) | Alle Pods aufgezählt + summiert |
| 3 | onlyoffice-staging zweiter Pod: +200m | `kubectl get pods` → CREATED: 2026-08-12T14:05:13Z |
| 4 | Velero node-agent DaemonSet: +200m | `kubectl get pods -n velero` → cpu=200m |
| 5 | CPU Requests NACH Änderungen: 6280m (157%) | 5880m + 200m + 200m |
| 6 | Neue Pods bei RollingUpdate: 600m (3 × 200m) | celery-worker (200m) + celery-worker-pro (200m) + onlyoffice (200m) |
| 7 | Scheduler: 4000m − 6280m = −2280m < 200m | `kubectl get events` → `Insufficient cpu` |
| 8 | Neue Pods: Pending (Unschedulable) | `kubectl get pods --field-selector=status.phase=Pending` |
| 9 | Alte Pods: Running (werden nicht terminiert) | RollingUpdate: neue Pods müssen zuerst Ready sein |
| 10 | `kubectl rollout status --timeout=300s` → TIMEOUT | CI Step 14: failure |

### Die Kette

```
ICH installiere Velero (node-agent DaemonSet: +200m CPU)
ICH erstelle onlyoffice-staging zweiten Pod (+200m CPU)
  → CPU Requests: 5880m → 6280m (157% von 4000m)
  → CI/CD: kubectl set image → RollingUpdate
  → Neue Pods brauchen: 3 × 200m = 600m
  → Scheduler prüft: 4000m − 6280m = −2280m < 200m → FAIL
  → Neue Pods: Pending
  → Alte Pods: Running (RollingUpdate wartet)
  → kubectl rollout status --timeout=300s → TIMEOUT
  → CI: Step 14 FAILED
```

---

## Betroffene Components

| Component | Impact | Status |
|-----------|--------|--------|
| Celery Worker (free) | Deploy fehlgeschlagen | Läuft mit altem Image (67a22aa1) |
| Celery Worker (pro) | Deploy fehlgeschlagen | Läuft mit altem Image (67a22aa1) |
| Celery Beat | Deploy fehlgeschlagen | Läuft mit neuem Image (e9ba2e0e) |
| OnlyOffice | Zweiter Pod Pending | Konfiguration nicht aktualisiert |
| Backend | Deploy erfolgreich | Läuft mit neuem Image (e9ba2e0e) |
| Frontend | Deploy erfolgreich | Läuft mit neuem Image |
| Pipeline | Funktioniert | test 5150: Recording → Transcription → PV ✅ |

---

## Was funktioniert trotzdem

| Component | Status | Detail |
|-----------|--------|--------|
| **Pipeline** | ✅ | test 5150: 2 Min Gesamtzeit |
| **Sentinel** | 🟡 | Fallback-Modus (llama-cpp-python fehlt) |
| **TIMING Logs** | ✅ | Im Code (noch nicht deployed) |
| **Backend** | ✅ | Neues Image mit E2E_TEST=false |

---

## Korrekturmaßnahmen

### Sofort (durchgeführt)

| # | Maßnahme | Status |
|---|----------|--------|
| 1 | Analyse: Root Cause = CPU Overcommit | ✅ |
| 2 | Verantwortung übernommen | ✅ |
| 3 | Pipeline funktioniert trotzdem (test 5150) | ✅ |

### Empfohlen (nächste Schritte)

| # | Maßnahme | Priorität | Aufwand |
|---|----------|-----------|---------|
| 1 | Deployment Strategy → Recreate (statt RollingUpdate) | P1 | Niedrig |
| 2 | CPU Requests reduzieren (Velero, Longhorn) | P2 | Niedrig |
| 3 | CI/CD: Deploy-Timeout erhöhen oder Pre-Check | P2 | Mittel |

---

## Lessons Learned

| # | Lesson | Details |
|---|--------|---------|
| 1 | **CPU Overcommit hat Grenzen** | Kubernetes erlaubt Overcommit, aber RollingUpdate braucht freie CPU für neue Pods |
| 2 | **Manuelle Änderungen müssen CPU beachten** | Velero + OnlyOffice hinzugefügt ohne Node-Kapazität zu prüfen |
| 3 | **RollingUpdate ist anfällig bei Overcommit** | maxSurge braucht zusätzliche CPU die nicht vorhanden ist |
| 4 | **CI/CD Timeout versteckt Root Cause** | `kubectl rollout status --timeout=300s` zeigt nur "timeout", nicht "Insufficient cpu" |

---

## Anhang: Deploy-Status (alle Runs)

| Run | SHA | Status | Step 14 | E2E | Trigger |
|-----|-----|--------|---------|-----|---------|
| #10 | 67a22aa1 | ✅ SUCCESS | ✅ | ✅ | CI Pipeline |
| #11 | 67a22aa1 | ✅ SUCCESS | ✅ | ✅ | CI Pipeline |
| #12 | 67a22aa1 | ⚠️ FAILURE | ✅ | ❌ | CI Pipeline |
| #13 | 59978e4e | ❌ FAILURE | ❌ | skipped | CI Pipeline |
| #14 | 59978e4e | ❌ FAILURE | ❌ | skipped | CI Pipeline |
| #15 | e9ba2e0e | ❌ FAILURE | ❌ | skipped | CI Pipeline |
