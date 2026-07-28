# Korrektur-Prompt — Plan-Verifizierung & Fehlerbehebung

Du bist ein Agent, der auf dem **Contabo-Produktionsserver (169.58.83.32)** arbeitet. Der vorherige Plan enthielt 4 schwere Fehler. Deine Aufgabe:

1. **Die 4 Fehler korrigieren**
2. **Offene Tasks verifizieren und priorisieren**
3. **Sicherstellen, dass alle Dateien existieren und funktionieren**

---

## Die 4 Fehler (korrigiert)

### ❌ Fehler 1: "Uncommitted changes — erledigt"
**Realität:** `git status` zeigt 6 geänderte + 11 neue Dateien. NICHTS davon committed.

**Zu committende Dateien:**
```
M  .github/workflows/deploy-production.yml  (Secrets-Logik: nur anwenden wenn nicht vorhanden)
M  .gitignore                               (infrastructure/kubernetes/production/*-secrets.yaml ausgeschlossen)
M  .loop.md                                 (geändert)
M  docker-compose.prod.yml                  (geändert)
M  infrastructure/.../onlyoffice-deployment.yaml (initContainer + emptyDir + SECURE_LINK_SECRET)
?? infrastructure/.../onlyoffice-configmap.yaml  (NEU — ConfigMap mit local.json + ds-docservice.conf)
?? infrastructure/.../secrets-template.yaml      (NEU — Secret-Struktur ohne Werte)
```

**Aktion:** Diese Dateien committen und pushen.

### ❌ Fehler 2: "deploy-production.yml existiert NICHT"
**Realität:** Datei EXISTIERT und funktioniert:
```
.github/workflows/deploy-production.yml (4055 bytes, heute 2x getestet)
```
- Trigger: `workflow_run` nach `docker-build.yml`
- Inhalt: SCP manifests → SSH → pull images → import containerd → apply → rollout restart
- **Smoke-Test fehlt:** Nach Rollout gibt es keinen Health-Check

**Aktion:** Smoke-Test hinzufügen (curl Health + Login nach Rollout).

### ❌ Fehler 3: "ingress-prod.yaml existiert NICHT"
**Realität:** Datei EXISTIERT:
```
infrastructure/kubernetes/production/ingress-prod.yaml (2034 bytes)
```
Enthält bereits:
- `/api` → backend:8000
- `/livekit` → backend:8000
- `/rtc` → livekit-server:7880
- `/twirp` → livekit-server:7880
- `/doc` → onlyoffice:80 ✅
- `/web-apps` → onlyoffice:80 ✅
- `/cache` → onlyoffice:80 ✅
- `/healthcheck` → onlyoffice:80 ✅
- `/` → frontend:80

**Aktion:** Prüfen ob Ingress auf Production applyt ist. Wenn nicht: `kubectl apply -f ingress-prod.yaml`.

### ❌ Fehler 4: "Staging: Braucht SSH (nicht von dieser Maschine)"
**Realität:** `~/.kube/config-staging` EXISTIERT und funktioniert:
```bash
kubectl --kubeconfig ~/.kube/config-staging get nodes
# NAME                     STATUS   ROLES    AGE   VERSION
# instance-20260329-0846   Ready    <none>   34d   v1.35.5+k3s1
```
**Kein SSH nötig** für Staging-Operationen via kubectl.

**Aktion:** Staging 854 evicted Pods via kubectl aufräumen:
```bash
kubectl --kubeconfig ~/.kube/config-staging delete pods --all-namespaces \
  --field-selector=status.phase=Failed --grace-period=0 --force
```

---

## Verifikations-Checkliste (VOR jeder Aktion)

**LESE IMMER ZUERST:**
1. `git status` — Was ist tatsächlich geändert?
2. `ls -la` — Existieren Dateien wirklich?
3. `kubectl get` — Was läuft auf dem Cluster?
4. **NIE** blind einen Plan ausführen. Immer verifizieren.

---

## Offene Tasks (nach Korrektur)

### Sofort (heute)
| # | Task | Befehl |
|---|------|--------|
| 1 | Uncommitted changes committen | `git add -A && git commit -m "feat: onlyoffice prod + secrets security + deploy workflow" && git push` |
| 2 | Smoke-Test zu deploy-production.yml hinzufügen | `curl` Health + Login nach Rollout |
| 3 | Ingress-prod.yaml auf Production applyn (falls nicht) | `kubectl apply -f ingress-prod.yaml` |
| 4 | Staging evicted Pods aufräumen | `kubectl delete pods --all-namespaces --field-selector=status.phase=Failed` |

### Diese Woche
| # | Task | Details |
|---|------|---------|
| 5 | CNPG 3 instances prüfen | `kubectl get pods -n meeting-automation -l cnpg.io/cluster` |
| 6 | n8n Workflows aktivieren | DB-Update: `UPDATE workflow_entity SET active = true WHERE ...` |
| 7 | Prometheus/Grafana applyn | `kubectl apply -f infrastructure/kubernetes/production/monitoring/` |
| 8 | OnlyOffice E2E Test | Editor-Route testen (nicht nur Healthcheck) |

### Nächstes Sprint
| # | Task | Details |
|---|------|---------|
| 9 | Pipeline-Perf ≤90s | Adaptive Gladia-Polling (docs/PIPELINE_QUICK_WINS.md) |
| 10 | Staging CI/CD | deploy-staging.yml erstellen |
| 11 | Backend CI Linting | 678 Issues in Batches fixen |

---

## Produktions-Zugang

**Server:** 169.58.83.32 (Contabo)
**SSH:** `root` oder `meeting` (Key: `~/.ssh/meeting`)
**Kubeconfig:** `~/.kube/config-prod` oder direkt `/etc/rancher/k3s/k3s.yaml`

**Staging:** 158.180.18.110 (OCI)
**Kubeconfig:** `~/.kube/config-staging` (funktioniert von dieser Maschine)

---

## HARTE REGELN (aus .loop.md)

1. **NIE `docker system prune`** auf k3s Nodes
2. **NIE Secrets committen**
3. **NIE Monitoring löschen** (Löschen ist verboten)
4. **IMMER `client_id` filtern** bei DB-Queries
5. **IMMER `audit_service.log_action()`** bei Datenänderungen
6. **OnlyOffice:** `storage.externalHost` muss mit Domain übereinstimmen
7. **CNPG:** `MINIO_ACCESS_KEY`/`MINIO_SECRET_KEY` (nicht `MINIO_ROOT_*`)

---

## Deine erste Aktion

```bash
# 1. Git-Status prüfen
cd /home/opc/meeting-automation && git status

# 2. Uncommitted changes committen
git add -A && git commit -m "feat: onlyoffice prod configmap + secrets security + deploy workflow update" && git push

# 3. Production Ingress prüfen
export KUBECONFIG=~/.kube/config-prod
kubectl get ingress -n meeting-automation

# 4. Falls Ingress fehlt: anwenden
kubectl apply -f infrastructure/kubernetes/production/ingress-prod.yaml

# 5. Smoke-Test manuell verifizieren
curl -sf https://meeting-automation.com/ -o /dev/null -w "%{http_code}"
curl -sf -X POST https://meeting-automation.com/api/v1/auth/login -d "username=dg@meeting.tn&password=Password123!" -o /dev/null -w "%{http_code}"

# 6. Staging aufräumen
kubectl --kubeconfig ~/.kube/config-staging delete pods --all-namespaces --field-selector=status.phase=Failed --grace-period=0 --force 2>&1 | tail -5
```

**Danach:** Commit der Smoke-Test-Änderung an `deploy-production.yml`.
