# Kubernetes Deployment Workarounds & Known Issues

> **Datum**: 2026-05-23
> **Umgebung**: Docker Desktop K8s (kind-Cluster `desktop-control-plane`)
> **Status**: Alle 12 Pods Running ✅

---

## Quick Start: Clean Deploy

```bash
# 1. Alten Stack löschen
kubectl delete namespace meeting-automation 2>/dev/null

# 2. Setup-Script ausführen
bash setup-kubernetes.sh
```

> ⚠️ Das Script wird bei **Postgres wait** timeouten (DNS fehlt noch). Die folgenden Workarounds manuell anwenden.

---

## Workaround 1: Local-Path Provisioner installieren

**Problem**: PVCs bleiben im `Pending`-Status. Der `rancher.io/local-path` Provisioner ist im Cluster nicht als Pod vorhanden.

```bash
kubectl apply -f https://raw.githubusercontent.com/rancher/local-path-provisioner/v0.0.26/deploy/local-path-storage.yaml
kubectl wait --for=condition=ready pod -l app=local-path-provisioner -n local-path-storage --timeout=30s
```

**Root Cause**: Docker Desktop K8s / kind liefert den Provisioner nicht automatisch mit.

---

## Workaround 2: CoreDNS ConfigMap fixen

**Problem**: CoreDNS crashlooped mit `Unknown directive '}STUBDOMAINS'`. Die ConfigMap enthält nicht ersetzte Template-Variablen (`CLUSTER_DOMAIN`, `UPSTREAMNAMESERVER`, `STUBDOMAINS`).

```bash
kubectl create configmap coredns -n kube-system --from-literal=Corefile='.:53 {
    errors
    health {
      lameduck 5s
    }
    ready
    kubernetes cluster.local in-addr.arpa ip6.arpa {
      fallthrough in-addr.arpa ip6.arpa
    }
    prometheus :9153
    forward . /etc/resolv.conf
    cache 30
    loop
    reload
    loadbalance
}' --dry-run=client -o yaml | kubectl apply -f -

# CoreDNS neustarten
kubectl delete pod -n kube-system -l k8s-app=kube-dns
kubectl wait --for=condition=ready pod -n kube-system -l k8s-app=kube-dns --timeout=30s
```

**DNS-Test**:
```bash
kubectl run dns-test --rm -it --image=busybox:1.28 --restart=Never -- nslookup postgres.meeting-automation.svc.cluster.local
```

---

## Workaround 3: Redis Secret Key-Name

**Problem**: Redis Deployment erwartet Secret-Key `password`, aber `redis-secrets.yaml` enthält `REDIS_PASSWORD`.

**Fix**: `infrastructure/kubernetes/redis-secrets.yaml`:
```yaml
stringData:
  password: redis_password_prod  # NICHT REDIS_PASSWORD
```

Danach neu verschlüsseln und anwenden:
```bash
export SOPS_AGE_KEY_FILE=~/.config/sops/age/keys.txt
sops -e -i infrastructure/kubernetes/redis-secrets.yaml
sops -d infrastructure/kubernetes/redis-secrets.yaml | kubectl apply -f -
```

---

## Workaround 4: Backend PYTHONPATH

**Problem**: Alembic und entrypoint.sh finden das `app`-Modul nicht → `ModuleNotFoundError: No module named 'app'`.

**Fix 1 – entrypoint.sh** (`backend/entrypoint.sh` Zeile 47-49):
```bash
echo "=== Running Alembic Migrations (ISO 27001 compliant) ==="
export PYTHONPATH=/app
cd /app
alembic upgrade head
```

**Fix 2 – initContainer command** (`infrastructure/kubernetes/backend-deployment.yaml`):
```yaml
initContainers:
- name: alembic-migrate
  command: ["/bin/sh", "-c", "export PYTHONPATH=/app && cd /app && alembic upgrade head"]
```

**Fix 3 – Backend Container env** (gleiche Datei):
```yaml
containers:
- name: backend
  env:
  - name: PYTHONPATH
    value: "/app"
```

---

## Workaround 5: CELERY_BROKER_URL

**Problem**: Celery Worker crashlooped mit `ACCESS_REFUSED - Login was refused`. Der Default-Wert in `config.py` (`amqp://rabbit_user:rabbit_password@rabbitmq:5672//`) hat das falsche Passwort.

**Fix**: `CELERY_BROKER_URL` zu `backend-secrets.yaml` hinzufügen:
```yaml
stringData:
  CELERY_BROKER_URL: amqp://rabbit_user:rabbit_password_prod@rabbitmq:5672//
```

Neu verschlüsseln und anwenden:
```bash
export SOPS_AGE_KEY_FILE=~/.config/sops/age/keys.txt
sops -e -i infrastructure/kubernetes/backend-secrets.yaml
sops -d infrastructure/kubernetes/backend-secrets.yaml | kubectl apply -f -
kubectl rollout restart deployment/celery-worker -n meeting-automation
```

---

## Workaround 6: n8n DB-User und N8N_PORT

**Problem**: n8n crashlooped mit:
1. `password authentication failed for user "postgres"` – fehlender `DB_POSTGRESDB_USER`
2. `Invalid number value for N8N_PORT: tcp://10.96.98.113:5678` – K8s injectet den Service-Port als ENV-Variable

**Fix** (`infrastructure/kubernetes/n8n-deployment.yaml`):
```yaml
env:
- name: DB_POSTGRESDB_USER
  value: "meeting_user"
- name: N8N_PORT
  value: "5678"
```

---

## Workaround 7: Docker Images in den Cluster laden

**Problem**: `ErrImageNeverPull` – Frontend-Image ist auf dem Docker-Host, aber nicht im containerd des K8s-Nodes.

**Lösung**:
```bash
# Image bauen
docker build -t meeting-automation-frontend:latest -f frontend/Dockerfile frontend/

# Image in containerd des K8s-Nodes importieren
docker save meeting-automation-frontend:latest | docker exec -i desktop-control-plane ctr -n k8s.io images import -

# Deployment neustarten
kubectl rollout restart deployment/frontend -n meeting-automation
kubectl wait --for=condition=ready pod -l app=frontend -n meeting-automation --timeout=120s
```

**Hinweis**: Das Backend-Image muss ebenfalls so geladen werden, wenn es neu gebaut wird:
```bash
docker save meeting-automation-backend:latest | docker exec -i desktop-control-plane ctr -n k8s.io images import -
kubectl rollout restart deployment/backend -n meeting-automation
```

---

## Workaround 8: Terminating PVCs forcieren

**Problem**: PVCs hängen im `Terminating`-Status (Finalizer-Blockade), neue StatefulSets können nicht starten.

```bash
kubectl delete pvc -n meeting-automation <pvc-name> --force
```

**Betroffen**: `postgres-storage-postgres-0`, `rabbitmq-storage-rabbitmq-0`, `minio-storage-minio-0` nach Namespace-Wechsel oder StorageClass-Änderung.

---

## Workaround 9: SOPS age Key regenerieren

**Problem**: Alter age Key verloren → Production-Secrets nicht entschlüsselbar.

**Lösung**:
```bash
# 1. Neuen Key generieren
mkdir -p ~/.config/sops/age
age-keygen -o ~/.config/sops/age/keys.txt

# 2. Public Key notieren (Ausgabe: age1...)
cat ~/.config/sops/age/keys.txt

# 3. .sops.yaml aktualisieren
# creation_rules:
#   - path_regex: infrastructure/kubernetes/.*secrets\.yaml$
#     age: <NEUER_PUBLIC_KEY>

# 4. Alle Production-Secrets neu verschlüsseln
export SOPS_AGE_KEY_FILE=~/.config/sops/age/keys.txt
for f in infrastructure/kubernetes/*-secrets.yaml; do
  # Plaintext-Version erstellen, dann verschlüsseln
  sops -d "$f" > /tmp/$(basename "$f") 2>/dev/null || true
  sops -e -i "$f"
done

# 5. Secrets im Cluster aktualisieren
for f in infrastructure/kubernetes/*-secrets.yaml; do
  sops -d "$f" | kubectl apply -f -
done
```

---

## Vollständiger Deploy-Ablauf (mit allen Workarounds)

```bash
# === PHASE 0: Cleanup ===
kubectl delete namespace meeting-automation 2>/dev/null

# === PHASE 1: Setup-Script (läuft bis Postgres-Timeout) ===
bash setup-kubernetes.sh || true

# === PHASE 2: Workarounds anwenden ===
# 2a. Local-Path Provisioner
kubectl apply -f https://raw.githubusercontent.com/rancher/local-path-provisioner/v0.0.26/deploy/local-path-storage.yaml
kubectl wait --for=condition=ready pod -l app=local-path-provisioner -n local-path-storage --timeout=30s

# 2b. CoreDNS fixen
kubectl create configmap coredns -n kube-system --from-literal=Corefile='.:53 {
    errors
    health { lameduck 5s }
    ready
    kubernetes cluster.local in-addr.arpa ip6.arpa { fallthrough in-addr.arpa ip6.arpa }
    prometheus :9153
    forward . /etc/resolv.conf
    cache 30
    loop
    reload
    loadbalance
}' --dry-run=client -o yaml | kubectl apply -f -
kubectl delete pod -n kube-system -l k8s-app=kube-dns
kubectl wait --for=condition=ready pod -n kube-system -l k8s-app=kube-dns --timeout=30s

# 2c. PVCs die hängen bleiben forcieren
kubectl delete pvc -n meeting-automation --all --force 2>/dev/null || true

# 2d. Infrastructure neu starten (PVCs werden neu erstellt)
kubectl delete statefulset postgres rabbitmq minio -n meeting-automation
kubectl apply -f infrastructure/kubernetes/postgres-statefulset.yaml
kubectl apply -f infrastructure/kubernetes/rabbitmq-statefulset.yaml
kubectl apply -f infrastructure/kubernetes/minio-statefulset.yaml
kubectl wait --for=condition=ready pod -l app=postgres -n meeting-automation --timeout=120s

# === PHASE 3: Application Deploy ===
kubectl apply -f infrastructure/kubernetes/backend-deployment.yaml
kubectl apply -f infrastructure/kubernetes/celery-worker-deployment.yaml
kubectl apply -f infrastructure/kubernetes/celery-beat-deployment.yaml
kubectl apply -f infrastructure/kubernetes/n8n-deployment.yaml
kubectl apply -f infrastructure/kubernetes/frontend-deployment.yaml
kubectl apply -f infrastructure/kubernetes/traefik-rbac.yaml
kubectl apply -f infrastructure/kubernetes/traefik-deployment.yaml
kubectl apply -f infrastructure/kubernetes/traefik-middlewares.yaml
kubectl apply -f infrastructure/kubernetes/traefik-ingressroute.yaml

# === PHASE 4: Images laden (falls ErrImageNeverPull) ===
docker save meeting-automation-frontend:latest | docker exec -i desktop-control-plane ctr -n k8s.io images import -
kubectl rollout restart deployment/frontend -n meeting-automation

# === PHASE 5: Wait for all ===
kubectl wait --for=condition=ready pod -l app=backend -n meeting-automation --timeout=120s
kubectl wait --for=condition=ready pod -l app=frontend -n meeting-automation --timeout=120s
kubectl wait --for=condition=ready pod -l app=n8n -n meeting-automation --timeout=120s
kubectl wait --for=condition=ready pod -l app=celery-worker -n meeting-automation --timeout=60s

# === PHASE 6: Post-Setup ===
kubectl exec -i deployment/backend -n meeting-automation -- bash -c "export PYTHONPATH=/app && cd /app && alembic upgrade head"
kubectl exec -i statefulset/minio -n meeting-automation -- mc alias set myminio http://localhost:9000 minio_user minio_password_prod
kubectl exec -i statefulset/minio -n meeting-automation -- mc mb myminio/recordings --ignore-existing

# === PHASE 7: Verify ===
kubectl get pods -n meeting-automation
```

---

## Service-Zugriff

```bash
# Frontend
kubectl port-forward deployment/frontend 3000:80 --address 0.0.0.0 -n meeting-automation

# Backend API
kubectl port-forward deployment/backend 8000:8000 --address 0.0.0.0 -n meeting-automation

# n8n UI
kubectl port-forward deployment/n8n 5678:5678 --address 0.0.0.0 -n meeting-automation

# MinIO Console
kubectl port-forward statefulset/minio 9001:9001 --address 0.0.0.0 -n meeting-automation
```

---

## Erwarteter Endzustand

```
NAME                             READY   STATUS
backend-xxx-xxx                  1/1     Running
backend-xxx-xxx                  1/1     Running
celery-beat-xxx-xxx              1/1     Running
celery-worker-xxx-xxx            1/1     Running
frontend-xxx-xxx                 1/1     Running
frontend-xxx-xxx                 1/1     Running
minio-0                          1/1     Running
n8n-xxx-xxx                      1/1     Running
postgres-0                       1/1     Running
rabbitmq-0                       1/1     Running
redis-xxx-xxx                    1/1     Running
traefik-xxx-xxx                  1/1     Running
```
