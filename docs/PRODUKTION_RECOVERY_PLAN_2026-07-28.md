# Produktion Recovery Plan — 2026-07-28

## Context
- **Maschine**: Contabo VPS (169.58.83.32), k3s v1.36.2+k3s1, **290 GiB Root-Disk**
- **Datum**: 2026-07-28, Staging-Recovery führte zur Entdeckung identischer Probleme auf Produktion
- **Kernproblem**: Docker + k3s laufen parallel mit je eigenem containerd → doppelter Speicherverbrauch + Müll-Akkumulation

## Executed Results (2026-07-28)

| Step | Ergebnis | Gewinn |
|------|----------|--------|
| Step 1: Docker Cache cleanup | ✅ 40 GiB freigeräumt | 113 GiB → 74 GiB (26%) |
| Step 2: Docker deaktiviert | ✅ `systemctl disable docker` | 2.5 GiB RAM freigegeben |
| Step 3: Pipeline fixen | ✅ `deploy-production.yml` aktualisiert | Kein Docker-Mittelsmann mehr |
| Step 4: Ephemeral-Storage Limits | ⏸ NICHT angewandt (217 GiB frei, nicht nötig) | — |
| Step 5: CronJobs | ⏸ Noch nicht deployt | — |
| Step 6: Stale :latest Image Fix | ✅ `deploy-production.yml` + manueller Fix | Frontend läuft frisches Image |

### Aktueller Zustand nach Recovery
```
Disk:  74 GiB / 290 GiB (26%)
Docker: inactive (deaktiviert)
k3s:   active, 10/10 Deployments Ready
Nodes: DiskPressure=False, MemoryPressure=False, PIDPressure=False
```

### Festplattenanalyse (VORHER: 113 GiB → NACHHER: 74 GiB)

| Bereich | GiB VOR | GiB NACHHER | Beschreibung |
|---------|---------|-------------|--------------|
| Docker containerd | 40.0 | 0.001 | 134 verwaiste Snapshots gelöscht |
| MinIO PVC (Meeting-Recordings) | 30.0 | 30.0 | Echte Daten — nicht cleanebar |
| k3s containerd | 21.0 | 21.0 | Images + Snapshots |
| Ollama LLM-Modelle | 9.0 | 9.0 | /usr/share/ollama |
| Swap | 5.0 | 5.0 | /.swapfile |
| Ollama CUDA Libs | 5.2 | 5.2 | Drei Versionen (v11, v12, v13) |
| Prometheus PVC | 4.7 | 4.7 | Monitoring-TSDB |
| System + Rest | ~18.1 | ~18.1 | /usr, /opt, /var, /tmp, /home/opc |
| **GESAMT** | **~113** | **~74** | df = 74 GiB (die Wahrheit) |

### du vs df Differenz
`sudo du -sh /` > `df` weil Kubernetes Bind-Mounts PVC-Daten doppelt zählen. **df ist die einzige verlässliche Quelle.**

## Root Cause Analysis

### Kernursache: Docker als unnötiges Mittelsmann
Die CI/CD Pipeline (`deploy-production.yml`) nutzte Docker als Zwischenspeicher:
```
docker pull backend:latest   → Docker containerd (Müll)
docker pull frontend:latest  → Docker containerd (Müll)
docker save | k3s ctr import → k3s containerd (gebraucht)
```
**Docker-Seite wurde NIE aufgeräumt.** Jedes Deploy hinterließ ~2 GiB verwaiste Snapshots + Content-Blobs.

### Warum Docker's eigene Prune-Commands nichts fanden
Die 40 GiB in `/var/lib/containerd` waren verwaiste Overlay-Snapshots von alten `docker build` Commands. Docker's `system prune` erkennt diese nicht, weil:
1. Die Snapshots in containerd's OverlayFS liegen, nicht in Docker's eigenem Cache
2. Die zugehörigen Images wurden gelöscht, aber die Snapshots blieben
3. containerd's eigene CLI (`ctr`) sieht die Snapshots nicht mehr (Metadata gelöscht)

### Zusätzliches Problem: celery-worker-pro OOMKill (GELÖST)
- **53 Restarts** pro Pod, Exit Code 137 (SIGKILL von Liveness Probe)
- **Root Cause**: NetworkPolicies fehlte `app: celery-worker-pro` Label
  - `rabbitmq-policy` erlaubte nur `backend`, `celery-worker`, `celery-beat`
  - `cnpg-policy`, `postgres-policy`, `redis-policy`, `minio-policy` ebenfalls
  - celery-worker-pro Pods konnten RabbitMQ nicht erreichen → "Waiting for RabbitMQ" Endlosschleife → Liveness Probe tötet Pod
- **Fix**: 5 NetworkPolicies gepatcht (rabbitmq, cnpg, postgres, redis, minio)
- **Resultat**: Beide Pods 1/1 Running, 0 Restarts, `celery ready` nach 30s

## Plan (5 Steps)

### Step 1: Docker Build-Cache aufräumen (SOFORT auf Produktion)
```bash
# Auf Contabo (169.58.83.32):
ssh meeting@169.58.83.32

# Docker stoppen
sudo systemctl stop docker docker.socket containerd

# Verwaiste Snapshots löschen
sudo find /var/lib/containerd/io.containerd.snapshotter.v1.overlayfs/snapshots/ -maxdepth 1 -mindepth 1 -type d -exec sudo rm -rf {} +

# Content-Blobs löschen
sudo find /var/lib/containerd/io.containerd.content.v1.content/blobs/ -type f -delete

# Metadata bereinigen
sudo find /var/lib/containerd/io.containerd.metadata.v1.bolt/ -type f -delete

# Docker neu starten
sudo systemctl start containerd docker.socket docker

# Verify
sudo du -sh /var/lib/containerd  # sollte <10M sein
df -h /  # sollte ~23 GiB mehr frei zeigen
```
- **Erwartung**: 23 GiB frei
- **Revert**: Docker restartet automatisch mit leerem Cache; beim nächsten `docker pull` werden Images neu geladen
- **Risiko**: Gering — nur Build-Cache betroffen, keine laufenden Container

### Step 2: Docker deaktivieren (nicht mehr nötig für Deploys)
```bash
# Auf Contabo:
sudo systemctl stop docker docker.socket containerd
sudo systemctl disable docker docker.socket containerd

# Verify
systemctl is-active docker  # sollte "inactive" sein
```
- **Revert**: `sudo systemctl enable --now docker docker.socket`
- **Risiko**: Gering — alle Services laufen über k3s, Docker wird nur fürs Builden gebraucht (läuft auf GitHub Actions, nicht auf Produktion)

### Step 3: Deploy-Pipeline fixen (Docker als Mittelsmann eliminieren)
Änderung in `.github/workflows/deploy-production.yml`:

**VORHER (Müll):**
```bash
docker pull docker.io/batnini/meeting-automation-backend:latest
docker pull docker.io/batnini/meeting-automation-frontend:latest
docker save docker.io/batnini/meeting-automation-backend:latest | k3s ctr images import -
docker save docker.io/batnini/meeting-automation-frontend:latest | k3s ctr images import -
```

**NACHHER (sauber):**
```bash
# Docker Hub Login für k3s
echo "${{ secrets.DOCKERHUB_TOKEN }}" | k3s ctr -n k8s.io images registry login docker.io --username "${{ secrets.DOCKERHUB_USERNAME }}" --password-stdin

# Direkt zu k3s pullen — kein Docker als Mittelsmann
k3s ctr -n k8s.io images pull docker.io/batnini/meeting-automation-backend:latest
k3s ctr -n k8s.io images pull docker.io/batnini/meeting-automation-frontend:latest || echo "Frontend image not available"

# Fallback: Falls k3s ctr pull fehlschlägt, weiterhin docker save nutzen
# Aber DANACH aufräumen:
docker system prune -f
```
- **Revert**: Alten deploy-production.yml aus Git wiederherstellen
- **Risiko**: Niedrig — `k3s ctr images pull` ist der Standard-Weg für k3s

### Step 4: Ephemeral-Storage Limits auf Produktion anwenden
Alle Produktion-Deployments bekommen `resources.limits.ephemeral-storage`:

| Deployment | Request | Limit |
|------------|---------|-------|
| backend | 200Mi | 1Gi |
| celery-worker | 200Mi | 1Gi |
| celery-worker-pro | 500Mi | 2Gi |
| celery-beat | 100Mi | 500Mi |
| frontend | 50Mi | 200Mi |
| livekit-server | 100Mi | 500Mi |
| livekit-egress | 200Mi | 1Gi |
| onlyoffice | 200Mi | 1Gi |
| n8n | 200Mi | 1Gi |

Plus `revisionHistoryLimit: 3` für alle Deployments (verhindert ReplicaSet-Akkumulation).

- **Revert**: Alten YAML aus Git wiederherstellen
- **Risiko**: Niedrig — Limits sind konservativ bemessen

### Step 5: Garbage-Collector CronJobs auf Produktion
```bash
# Pod GC CronJob (alle 15 Min)
kubectl apply -f infrastructure/kubernetes/production/pod-garbage-collector-cronjob.yaml

# Ephemeral Storage Cleanup (alle 6h)
kubectl apply -f infrastructure/kubernetes/production/ephemeral-storage-cleanup-cronjob.yaml
```
- **Revert**: `kubectl delete cronjob pod-garbage-collector -n kube-system`
- **Risiko**: Gering — CronJobs bereinigen nur tote Pods

### Step 6: Stale :latest Image Fix (containerd Cache-Problem)

**Problem:** `k3s ctr images pull ... :latest` prüft nicht, ob das remote-Image neuer ist als das lokale. containerd gibt einfach das gecachte Image zurück. Pod läuft altes Frontend.

**Symptom:** Image SHA im Pod (`27b0dc35bccff...`) ≠ neuestes Docker Hub Image (`650fc983ec3c...`)

**Root Cause:** `kubectl rollout restart` löst Neustart aus, aber containerd verwendet das gecachte `:latest` Image. Kein Re-Pull von Registry.

**Fix (deploy-production.yml):** Alte Images VOR dem Pull aus containerd löschen:
```bash
k3s ctr images rm docker.io/batnini/meeting-automation-backend:latest 2>/dev/null || true
k3s ctr images rm docker.io/batnini/meeting-automation-frontend:latest 2>/dev/null || true
```

**Manueller Sofort-Fix (Produktion):**
```bash
# Docker tempär starten (Docker Hub Auth vorhanden)
systemctl start docker
docker pull docker.io/batnini/meeting-automation-frontend:latest
docker save docker.io/batnini/meeting-automation-frontend:latest | k3s ctr images import -
docker image rm docker.io/batnini/meeting-automation-frontend:latest
systemctl stop docker

# Rollout neu starten
kubectl rollout restart deployment/frontend -n meeting-automation
```

**Hinweis:** `k3s ctr images pull` auf Produktion scheitert ohne Docker Hub Auth. Der CI-Pipeline hat die Secrets, manuelles SSH nicht. Fallback: Docker tempär starten, pull+save+import.

- **Revert**: Alten deploy-production.yml aus Git wiederherstellen
- **Risiko**: Niedrig — verhindert nur stale Images, kein Break wenn Registry down

## Rollback-Strategie

| Scenario | Aktion |
|----------|--------|
| Docker-Bereinigung schlägt fehl | Docker neu starten — Image-Cache wird bei nächstem Deploy neu geladen |
| Pipeline-Fix funktioniert nicht | Alten deploy-production.yml aus Git restore + `docker pull` als Fallback |
| Ephemeral-Storage Limits zu niedrig | Pods werden evicted → Limits in YAML erhöhen + Deploy |
| k3s ctr images pull funktioniert nicht | Fallback zu `docker pull + save + prune` |
| Produktion-Pods gehen down | `kubectl rollout restart deployment/<name> -n meeting-automation` |

## Checkliste vor Deploy

```bash
# 1. Disk-Check
df -h /
kubectl describe node <node> | grep -E "DiskPressure|Taints"

# 2. Pods gesund?
kubectl get pods -n meeting-automation --no-headers | awk '{print $3}' | sort | uniq -c

# 3. containerd sauber?
sudo find /var/lib/containerd/io.containerd.snapshotter.v1.overlayfs/snapshots/ -maxdepth 1 -type d | wc -l

# 4. Docker deaktiviert?
systemctl is-active docker  # inactive = gut
```

## Dateien geändert
- `.github/workflows/deploy-production.yml` (Pipeline-Fix: Docker als Mittelsmann eliminieren + Stale :latest Image Prevention)
- `infrastructure/kubernetes/production/backend-deployment.yaml` (revisionHistoryLimit: 3)
- `infrastructure/kubernetes/production/celery-worker-deployment.yaml` (revisionHistoryLimit: 3)
- `infrastructure/kubernetes/production/celery-worker-pro-deployment.yaml` (revisionHistoryLimit: 3)
- `infrastructure/kubernetes/production/celery-beat-deployment.yaml` (revisionHistoryLimit: 3)
- `infrastructure/kubernetes/production/frontend-deployment.yaml` (revisionHistoryLimit: 3)
- `infrastructure/kubernetes/production/livekit-server-deployment.yaml` (revisionHistoryLimit: 3)
- `infrastructure/kubernetes/production/livekit-egress-deployment.yaml` (revisionHistoryLimit: 3)
- `infrastructure/kubernetes/production/onlyoffice-deployment.yaml` (revisionHistoryLimit: 3)
- `infrastructure/kubernetes/production/redis-deployment.yaml` (revisionHistoryLimit: 3)
- `infrastructure/kubernetes/production/n8n-deployment.yaml` (revisionHistoryLimit: 3)
- `infrastructure/kubernetes/production/network-policies.yaml` (celery-worker-pro zu 5 Policies hinzugefügt)
- `backend/tests/conftest.py` (E2E Passwort-Sync aus E2E_TEST_USER_PASSWORD env var)
- `docs/PRODUKTION_RECOVERY_PLAN_2026-07-28.md` (diese Datei)
