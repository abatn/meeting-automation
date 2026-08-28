# Incident Report: Velero Deploy-Blocker + Ressourcenverschwendung

**Datum:** 2026-08-27  
**Betroffene Systeme:** Staging (158.180.18.110) + Production (169.58.83.32)  
**Schweregrad:** P0 (Deploy-Blocker) / P1 (Ressourcenverschwendung)  
**Status:** Behoben

---

## Zusammenfassung

Zwei Probleme im Zusammenhang mit der Velero-Skalierungsstrategie wurden identifiziert:

1. **Production Velero Node-Agent läuft unnötig** — Deploy 0/0 aber Node-Agent DaemonSet 1/1
2. **CI/CD Deploys blockiert** — Beide `04-velero-scope-check.sh` Scripts brechen mit `exit 1` ab wenn Velero intentional auf 0 skaliert ist

---

## Problem 1: Production Velero Node-Agent DaemonSet (Ressourcenverschwendung)

### Symptom
- Velero Deployment: `replicas=0` (korrekt skaliert)
- Velero Node-Agent DaemonSet: `desired=1, ready=1` (NICHT skaliert)
- Verbraucht: 14m CPU, 25Mi RAM unnötig

### Ursache
Bei der Skalierung von Velero wurde nur das Deployment auf 0 gesetzt, aber der Node-Agent DaemonSet nicht berücksichtigt. Auf Staging wurde der Node-Agent korrekt über `nodeSelector: non-existing=true` gestoppt.

### Lösung
Node-Agent DaemonSet mit demselben `non-existing=true` nodeSelector skalieren wie bei Staging.

### Befehle

```bash
# Production
kubectl patch ds node-agent -n velero -p '{"spec":{"template":{"spec":{"nodeSelector":{"non-existing":"true"}}}}}'

# Verifikation
kubectl get ds node-agent -n velero
# Erwartet: desired=0, ready=0

# Rollback (falls doch benötigt)
kubectl patch ds node-agent -n velero -p '{"spec":{"template":{"spec":{"nodeSelector":{}}}}}'
```

---

## Problem 2: CI/CD Deploy-Blocker (exit 1 bei skaliertem Velero)

### Symptom
```
=== Velero Scope Check ===
❌ Velero Schedule hat keinen/falschen Selector!
   Deploy abgebrochen.
```

Deploy-Scripts `04-velero-scope-check.sh` (beide Cluster) brechen mit `exit 1` ab wenn:
- Velero nicht läuft (Deploy replicas=0, node-agent 0/0)
- Velero Schedule nicht erreichbar ist

### Ursache
Die Scripts prüfen Velero-Konfiguration ohne zuvor zu prüfen ob Velero überhaupt läuft. Es fehlt ein Guard-Clause der bei gestopptem Velero die Checks überspringt.

### Betroffene Dateien
- `scripts/deploy-staging/04-velero-scope-check.sh` (Zeile 17-18, 28-29)
- `scripts/deploy-prod/04-velero-scope-check.sh` (Zeile 17-18, 28-29)

### Lösung
Guard-Clause am Anfang beider Scripts einbauen:
```bash
# Skip if Velero is intentionally scaled down
VELERO_DESIRED=$(kubectl get ds node-agent -n velero -o jsonpath='{.spec.desiredNumberScheduled}' 2>/dev/null || echo "0")
if [ "$VELERO_DESIRED" = "0" ]; then
  echo "⚠️ Velero node-agent scaled to 0 — skipping scope check"
  exit 0
fi
```

### Verifikation
```bash
# Test: Scripts müssen exit 0 geben wenn Velero auf 0 ist
bash scripts/deploy-staging/04-velero-scope-check.sh  # muss exit 0
bash scripts/deploy-prod/04-velero-scope-check.sh     # muss exit 0
```

### Rollback
Änderungen rückgängig machen durch Entfernen der Guard-Clause.

---

## Problem 3: CI/CD Backup-Job hängt wenn Velero auf 0 ist

### Symptom
- Deploy Production `pre-deploy-backup` Job hängt 10+ Minuten
- Velero Backup CRD `pre-deploy-cb787c39` wird erstellt aber nie verarbeitet
- Kein Velero Server da (0/0) → `--wait` wartet endlos

### Ursache
`deploy-production.yml` prüft nur ob Velero Deployment **existiert** (`kubectl get deployment`), nicht ob es **readyReplicas > 0** hat. Bei 0/0 existiert die Deployment-Resource trotzdem → Check besteht → Backup CRD wird erstellt → kein Server → Hängt.

### Lösung
Zusätzliche Prüfung auf `readyReplicas` in `deploy-production.yml`:
```bash
VELERO_READY=$(kubectl get deployment velero -n velero -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
if [ -z "$VELERO_READY" ] || [ "$VELERO_READY" = "0" ]; then
  echo "⚠️ Velero deployment exists but NOT running — skipping backup"
  exit 0
fi
```

### Verifikation
- Deploy Production mit gestopptem Velero → Backup wird übersprungen (exit 0)
- Deploy Production mit laufendem Velero → Backup wird ausgeführt

---

## Timeline

| Zeit | Aktion |
|------|--------|
| 2026-08-27 | Incident identifiziert |
| 2026-08-27 | Staging Verifikation abgeschlossen |
| 2026-08-27 | Production Verifikation abgeschlossen |
| 2026-08-27 | Fix implementiert (Problem 1+2) |
| 2026-08-27 | Verifikation auf beiden Clustern |
| 2026-08-27 | Problem 3 identifiziert (Backup-Job hängt) |
| 2026-08-27 | Fix implementiert (Problem 3: readyReplicas Check) |

---

## Verifikationstabelle

| # | Prüfpunkt | Staging | Production |
|---|-----------|---------|------------|
| 1 | Velero Deploy replicas=0 | ✅ | ✅ |
| 2 | Velero node-agent DaemonSet 0/0 | ✅ | ❌ → ✅ (nach Fix) |
| 3 | Guard-Clause in Scripts | ❌ → ✅ (nach Fix) | ❌ → ✅ (nach Fix) |
| 4 | Deploy-Script exit 0 bei gestopptem Velero | ❌ → ✅ (nach Fix) | ❌ → ✅ (nach Fix) |

---

## Betroffene Komponenten

| Komponente | Staging | Production |
|------------|---------|------------|
| Velero Deploy | 0/0 ✅ | 0/0 ✅ |
| Velero Node-Agent | 0/0 ✅ | 1/1 ❌ → 0/0 ✅ |
| 04-velero-scope-check.sh | exit 1 ❌ → exit 0 ✅ | exit 1 ❌ → exit 0 ✅ |
| deploy-staging.yml | Blockiert ❌ → Freigegeben ✅ | — |
| deploy-production.yml | — | Blockiert ❌ → Freigegeben ✅ |

---

## Root Cause

Die Velero-Skalierungsstrategie (Velero gestoppt spart Ressourcen wenn keine Backups benötigt werden) wurde nicht in die CI/CD-Pipeline integriert. Zwei Probleme:
1. Deploy-Scripts prüfen Velero-Konfiguration ohne Guard-Clause für gestoppten Zustand
2. Deploy-Workflow prüft Velero-Existenz, nicht Velero-Readiness → Backup-Job hängt endlos

## Lessons Learned

1. **Skalierungsstrategie muss in CI/CD integriert sein** — Jede Komponente die gestoppt werden kann braucht Guard-Clauses in abhängigen Scripts
2. **DaemonSets brauchen explizite Skalierung** — Deployments auf 0 zu setzen reicht nicht wenn DaemonSets existieren
3. **Guard-Clauses vor kubectl-Befehlen** — Prüfen ob Ressource existiert bevor Config abgefragt wird
4. **Deployment-Existenz ≠ Deployment-Bereitschaft** — `kubectl get deployment` prüft Existenz, `readyReplicas` prüft ob der Server tatsächlich läuft. Für `--wait` Befehle muss beides geprüft werden
