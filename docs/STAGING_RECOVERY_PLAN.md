# Staging Cluster — Recovery & Rekonstruktionsplan

> **Aktualisiert**: 2026-06-23 | k3s Migration abgeschlossen

**Erstellt:** 2026-04-05  
**Kontext:** Dokumentiert alle Probleme und Lösungen aus der Wiederherstellungssession nach versehentlichem Cluster-Löschen.  
**Status:** Kind-basiertes Setup ist HISTORISCH. Aktuelles Setup: k3s v1.35.5+k3s1 auf OCI VM.

---

## Architektur-Übersicht (AKTUELL: k3s)

```
Host (Oracle Cloud ARM64 aarch64, 158.180.18.110)
│
├── k3s v1.35.5+k3s1
│   └── Namespace: meeting-automation-staging
│       ├── postgres-staging (StatefulSet, PVC)
│       ├── redis-staging (StatefulSet, PVC)
│       ├── rabbitmq-staging (StatefulSet, PVC)
│       ├── minio-staging (StatefulSet, PVC)
│       ├── n8n-staging (Deployment, PVC)
│       ├── onlyoffice-staging (Deployment, PVC)
│       ├── backend-staging (2x Deployment)
│       ├── celery-worker-staging (Deployment)
│       ├── celery-beat-staging (Deployment)
│       ├── frontend-staging (Deployment, NodePort 31362)
│       ├── livekit-server-staging (Deployment, hostNetwork)
│       └── livekit-egress-staging (Deployment, hostNetwork)
│
└── Docker Daemon (nur für lokale Entwicklung)
```

---

## Architektur-Übersicht (HISTORISCH: Kind)

```
Host (Oracle Cloud ARM64 aarch64)
│
├── Docker Daemon
│   ├── Kind Cluster: meeting-staging
│   │   ├── Node: meeting-staging-control-plane (Docker Container)
│   │   │   └── extraMounts:
│   │   │       ├── /home/opc/meeting-automation/data/postgres → /data/postgres
│   │   │       └── /home/opc/meeting-automation/data/minio   → /data/minio
│   │   └── Namespace: meeting-automation-staging
│   │       ├── backend (2x), celery-worker, celery-beat
│   │       ├── postgres (hostPath: /data/postgres) ← PERSISTENT
│   │       ├── redis, rabbitmq
│   │       ├── minio (hostPath: /data/minio)       ← PERSISTENT
│   │       ├── n8n, onlyoffice, frontend
│   │       └── traefik (kube-system, NodePort 30080)
│   │
│   ├── docker-compose Stack (DEV)
│   │   └── Alle Services auf Standard-Ports (Frontend: 3000)
│   │
│   └── local-registry Container (172.18.0.4:5000)
│       └── Alle Images für offline Kind-Loading
│
└── Persistente Daten
    ├── /home/opc/meeting-automation/data/postgres/  (PostgreSQL WAL + Tabellen)
    └── /home/opc/meeting-automation/data/minio/     (S3 Buckets)
```

---

## Bekannte Probleme & Lösungen

### Problem 1: Kind kann keine Multi-arch Images laden (KRITISCH)

**Symptom:** `kind load docker-image postgres:15-alpine` → `ctr: content digest not found`  
**Ursache:** ARM64 (aarch64) + Docker speichert Multi-arch Manifest-Lists. `kind load` und `ctr import` können Docker-Format Manifest-Lists nicht verarbeiten.  
**Betroffen:** postgres, redis, rabbitmq, minio, n8n, onlyoffice, traefik  
**Nicht betroffen:** Custom-gebaute Single-arch Images (backend, frontend) → `kind load` funktioniert  

**Lösung:** Lokale Docker Registry als Brücke nutzen:
```bash
# Registry starten (im kind Netzwerk)
docker run -d --name local-registry --network kind -p 5001:5000 registry:2

# Docker Daemon für HTTP Registry konfigurieren
sudo bash -c 'cat > /etc/docker/daemon.json << EOF
{"insecure-registries": ["172.18.0.4:5000", "localhost:5001"]}
EOF'
sudo systemctl reload docker

# Registry IP ermitteln
REGISTRY=$(docker inspect local-registry --format '{{.NetworkSettings.Networks.kind.IPAddress}}'):5000

# Alle Images in Registry pushen
for img in traefik:v3.6.12 meeting-automation-backend:latest meeting-automation-frontend:staging \
  postgres:15-alpine redis:7-alpine rabbitmq:3-management-alpine \
  minio/minio:latest n8nio/n8n:latest onlyoffice/documentserver:latest; do
  docker tag "$img" "$REGISTRY/$img"
  docker push "$REGISTRY/$img"
done

# Images via ctr --plain-http in Kind-Node laden und taggen
NODE="meeting-staging-control-plane"
declare -A ALIASES=(
  ["${REGISTRY}/traefik:v3.6.12"]="docker.io/library/traefik:v3.6.12"
  ["${REGISTRY}/postgres:15-alpine"]="docker.io/library/postgres:15-alpine"
  ["${REGISTRY}/redis:7-alpine"]="docker.io/library/redis:7-alpine"
  ["${REGISTRY}/rabbitmq:3-management-alpine"]="docker.io/library/rabbitmq:3-management-alpine"
  ["${REGISTRY}/minio/minio:latest"]="docker.io/minio/minio:latest"
  ["${REGISTRY}/n8nio/n8n:latest"]="docker.io/n8nio/n8n:latest"
  ["${REGISTRY}/onlyoffice/documentserver:latest"]="docker.io/onlyoffice/documentserver:latest"
  ["${REGISTRY}/meeting-automation-backend:latest"]="docker.io/library/meeting-automation-backend:latest"
  ["${REGISTRY}/meeting-automation-frontend:staging"]="docker.io/library/meeting-automation-frontend:staging"
)
for SRC in "${!ALIASES[@]}"; do
  DST="${ALIASES[$SRC]}"
  docker exec "$NODE" ctr -n k8s.io images pull --plain-http "$SRC"
  docker exec "$NODE" ctr -n k8s.io images tag "$SRC" "$DST" 2>/dev/null || true
done
```

---

### Problem 2: `imagePullPolicy: Always` verhindert lokale Image-Nutzung

**Symptom:** Pods in `ImagePullBackOff` obwohl Image in containerd vorhanden  
**Ursache:** `imagePullPolicy: Always` zwingt Kubernetes von Docker Hub zu pullen  
**Betroffen:** n8n, onlyoffice, minio, alle Services ohne explizites `IfNotPresent`  

**Lösung:** Alle Deployments/StatefulSets patchen:
```bash
export KUBECONFIG=/home/opc/meeting-automation/kubeconfig-staging.txt
for resource in \
  "deployment/n8n-staging" "deployment/onlyoffice-staging" \
  "statefulset/minio-staging" "statefulset/postgres-staging" \
  "statefulset/rabbitmq-staging" "deployment/redis-staging" \
  "deployment/backend" "deployment/celery-worker-staging" \
  "deployment/celery-beat-staging" "deployment/frontend"; do
  kubectl patch "$resource" -n meeting-automation-staging \
    --type='json' \
    -p='[{"op":"replace","path":"/spec/template/spec/containers/0/imagePullPolicy","value":"IfNotPresent"}]'
done
```

**Dauerlösung:** `imagePullPolicy: IfNotPresent` direkt in alle YAML-Manifests eintragen.

---

### Problem 3: setup-staging-cluster.sh verwendet falschen kubeconfig

**Symptom:** Script deployt alle Manifests in `kind-kind` statt `meeting-staging`  
**Ursache:** Script nutzt `KUBECONFIG_PATH="${HOME}/.kube/config"` als Default. `~/.kube/config` hatte `staging-cluster` noch auf `kind-kind` gemappt.  

**Lösung:** Script immer mit explizitem kubeconfig aufrufen:
```bash
./scripts/setup-staging-cluster.sh --env local \
  --kubeconfig /home/opc/meeting-automation/kubeconfig-staging.txt
```

Oder vorher sicherstellen:
```bash
kubectl config get-contexts --kubeconfig ~/.kube/config
# staging-cluster muss auf meeting-staging zeigen, nicht auf kind-kind
```

---

### Problem 4: Alembic Bug in Migration 4fb76575fee0

**Symptom:** `alembic upgrade head` schlägt fehl mit `column "language" does not exist`  
**Ursache:** Migration `e9dd04c9d6f1` erstellt `action_suggestions` OHNE `language` Spalte. Migration `4fb76575fee0` (anderer Branch) versucht `ALTER COLUMN language` → Fehler.  

**Lösung:** 2-Phasen-Migration:
```bash
BACKEND_POD=$(kubectl get pods -n meeting-automation-staging -l app=backend \
  -o jsonpath='{.items[0].metadata.name}')

# Phase 1: Bis vor den Bug-Stand
kubectl exec -n meeting-automation-staging "$BACKEND_POD" -- \
  bash -c "cd /app && PYTHONPATH=/app alembic upgrade e9dd04c9d6f1"

# Phase 2: Spalte manuell hinzufügen
kubectl exec -i postgres-staging-0 -n meeting-automation-staging -- \
  psql -U meeting_user -d meeting_db_staging -c \
  "ALTER TABLE action_suggestions ADD COLUMN IF NOT EXISTS language VARCHAR(10) DEFAULT 'en' NOT NULL;"

# Phase 3: Rest der Migrationen
kubectl exec -n meeting-automation-staging "$BACKEND_POD" -- \
  bash -c "cd /app && PYTHONPATH=/app alembic upgrade head"
```

**Falls Tabellen bereits existieren** (Backend hat auto-create_all gemacht):
```bash
kubectl exec -n meeting-automation-staging "$BACKEND_POD" -- \
  bash -c "cd /app && PYTHONPATH=/app alembic stamp head"
```

---

### Problem 5: Kind-Cluster kubeconfig nicht in ~/.kube/config

**Symptom:** `kubectl config rename-context kind-meeting-staging staging-cluster` → `not in /home/opc/.kube/config`  
**Ursache:** `kind create cluster` schreibt in `~/.kube/config` aber nur wenn kein KUBECONFIG env gesetzt. Bei bestehender custom kubeconfig-staging.txt wird der neue Cluster separat gespeichert.  

**Lösung:** kubeconfig direkt von Kind holen und Context umbenennen:
```bash
kind get kubeconfig --name meeting-staging > /home/opc/meeting-automation/kubeconfig-staging.txt
sed -i 's/kind-meeting-staging/staging-cluster/g' \
  /home/opc/meeting-automation/kubeconfig-staging.txt
```

---

### Problem 6: Backend crasht beim Start (MinIO nicht bereit)

**Symptom:** Backend in `CrashLoopBackOff` mit `EndpointConnectionError: minio-staging:9000`  
**Ursache:** Backend startet bevor MinIO Running ist. MinIO war wegen `imagePullPolicy: Always` in ImagePullBackOff.  
**Lösung:** MinIO zuerst Running sicherstellen (Problem 1+2 lösen), dann Backend rollt automatisch weiter.

---

### Problem 7: containerd config_path — falscher Key

**Symptom:** `hosts.toml` für lokale Registry wird ignoriert  
**Ursache:** Falscher Key `registry_config_path` statt korrektem Ansatz  
**Lösung:** Nicht `/etc/containerd/config.toml` editieren. Stattdessen `ctr --plain-http` verwenden (siehe Problem 1).

---

## Vollständige Recovery-Prozedur (von Null)

### Voraussetzungen prüfen
```bash
kind version          # mind. v0.20
kubectl version       # mind. 1.28
helm version          # mind. v3
docker version        # mind. 24
```

### Schritt 1: Datenpersistenz vorbereiten
```bash
mkdir -p /home/opc/meeting-automation/data/postgres
mkdir -p /home/opc/meeting-automation/data/minio
```

### Schritt 2: Kind Cluster erstellen
```bash
cd /home/opc/meeting-automation
kind create cluster --name meeting-staging --config kind-config-staging.yaml
kind get kubeconfig --name meeting-staging > kubeconfig-staging.txt
sed -i 's/kind-meeting-staging/staging-cluster/g' kubeconfig-staging.txt
export KUBECONFIG=/home/opc/meeting-automation/kubeconfig-staging.txt
```

### Schritt 3: Traefik installieren
```bash
helm repo add traefik https://helm.traefik.io/traefik
helm repo update
helm upgrade --install traefik traefik/traefik \
  --namespace kube-system \
  --set providers.kubernetesCRD.enabled=true \
  --set providers.kubernetesIngress.enabled=true \
  --set service.type=NodePort \
  --set "ports.web.nodePort=30080"
```

### Schritt 4: Custom Images laden (kind load — funktioniert für Single-arch)
```bash
kind load docker-image meeting-automation-backend:latest --name meeting-staging
kind load docker-image meeting-automation-frontend:staging --name meeting-staging
```

### Schritt 5: Multi-arch Images via lokale Registry laden
```bash
# Nur nötig wenn kein Internet im Kind-Node (Normalfall auf diesem Server)
# Vollständiges Script: siehe Problem 1 Lösung oben
docker run -d --name local-registry --network kind -p 5001:5000 registry:2 2>/dev/null || docker start local-registry
REGISTRY=$(docker inspect local-registry --format '{{.NetworkSettings.Networks.kind.IPAddress}}'):5000

for img in traefik:v3.6.12 postgres:15-alpine redis:7-alpine rabbitmq:3-management-alpine \
           minio/minio:latest n8nio/n8n:latest onlyoffice/documentserver:latest; do
  docker tag "$img" "$REGISTRY/$img" 2>/dev/null || true
  docker push "$REGISTRY/$img"
done

NODE="meeting-staging-control-plane"
for img in traefik:v3.6.12 postgres:15-alpine redis:7-alpine rabbitmq:3-management-alpine \
           minio/minio:latest n8nio/n8n:latest onlyoffice/documentserver:latest; do
  docker exec "$NODE" ctr -n k8s.io images pull --plain-http "$REGISTRY/$img"
done

# Originale Tags setzen
docker exec "$NODE" ctr -n k8s.io images tag "$REGISTRY/traefik:v3.6.12"              docker.io/library/traefik:v3.6.12
docker exec "$NODE" ctr -n k8s.io images tag "$REGISTRY/postgres:15-alpine"            docker.io/library/postgres:15-alpine
docker exec "$NODE" ctr -n k8s.io images tag "$REGISTRY/redis:7-alpine"                docker.io/library/redis:7-alpine
docker exec "$NODE" ctr -n k8s.io images tag "$REGISTRY/rabbitmq:3-management-alpine"  docker.io/library/rabbitmq:3-management-alpine
docker exec "$NODE" ctr -n k8s.io images tag "$REGISTRY/minio/minio:latest"            docker.io/minio/minio:latest
docker exec "$NODE" ctr -n k8s.io images tag "$REGISTRY/n8nio/n8n:latest"              docker.io/n8nio/n8n:latest
docker exec "$NODE" ctr -n k8s.io images tag "$REGISTRY/onlyoffice/documentserver:latest" docker.io/onlyoffice/documentserver:latest
```

### Schritt 6: Traefik Pod neu starten (damit er das geladene Image nutzt)
```bash
kubectl rollout restart deployment/traefik -n kube-system
kubectl rollout status deployment/traefik -n kube-system --timeout=60s
```

### Schritt 7: Namespace und Manifests deployen
```bash
kubectl apply -f infrastructure/kubernetes/staging/namespace.yaml
NS="meeting-automation-staging"
INFRA="infrastructure/kubernetes/staging"

for manifest in \
  postgres-secrets.yaml postgres-statefulset.yaml \
  redis-secrets.yaml redis-deployment.yaml \
  rabbitmq-secrets.yaml rabbitmq-statefulset.yaml \
  minio-secrets.yaml minio-statefulset.yaml \
  n8n-secrets.yaml n8n-deployment.yaml \
  onlyoffice-deployment.yaml \
  backend-secrets.yaml backend-config.yaml \
  celery-worker-deployment.yaml celery-beat-deployment.yaml \
  backend-deployment.yaml \
  traefik-middlewares.yaml traefik-ingressroute-local.yaml \
  frontend-deployment.yaml; do
  kubectl apply -f "${INFRA}/${manifest}" -n "$NS"
done
```

### Schritt 8: imagePullPolicy auf IfNotPresent setzen
```bash
for resource in \
  "deployment/n8n-staging" "deployment/onlyoffice-staging" \
  "statefulset/minio-staging" "statefulset/postgres-staging" \
  "statefulset/rabbitmq-staging" "deployment/redis-staging" \
  "deployment/backend" "deployment/celery-worker-staging" \
  "deployment/celery-beat-staging" "deployment/frontend"; do
  kubectl patch "$resource" -n meeting-automation-staging \
    --type='json' \
    -p='[{"op":"replace","path":"/spec/template/spec/containers/0/imagePullPolicy","value":"IfNotPresent"}]'
done
```

### Schritt 9: Auf alle Pods warten
```bash
kubectl wait --for=condition=ready pod -l app=postgres-staging \
  -n meeting-automation-staging --timeout=120s
kubectl wait --for=condition=ready pod -l app=backend \
  -n meeting-automation-staging --timeout=180s
```

### Schritt 10: Alembic Migration
```bash
BACKEND_POD=$(kubectl get pods -n meeting-automation-staging -l app=backend \
  -o jsonpath='{.items[0].metadata.name}')

# Prüfen ob Tabellen schon existieren
TABLES=$(kubectl exec -i postgres-staging-0 -n meeting-automation-staging -- \
  psql -U meeting_user -d meeting_db_staging -t -c \
  "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';")

if [ "$TABLES" -gt 5 ]; then
  echo "Tabellen existieren → stamp head"
  kubectl exec -n meeting-automation-staging "$BACKEND_POD" -- \
    bash -c "cd /app && PYTHONPATH=/app alembic stamp head"
else
  echo "Frische DB → 2-Phasen-Migration"
  kubectl exec -n meeting-automation-staging "$BACKEND_POD" -- \
    bash -c "cd /app && PYTHONPATH=/app alembic upgrade e9dd04c9d6f1"
  kubectl exec -i postgres-staging-0 -n meeting-automation-staging -- \
    psql -U meeting_user -d meeting_db_staging -c \
    "ALTER TABLE action_suggestions ADD COLUMN IF NOT EXISTS language VARCHAR(10) DEFAULT 'en' NOT NULL;"
  kubectl exec -n meeting-automation-staging "$BACKEND_POD" -- \
    bash -c "cd /app && PYTHONPATH=/app alembic upgrade head"
fi
```

### Schritt 11: MinIO Bucket erstellen
```bash
BACKEND_POD=$(kubectl get pods -n meeting-automation-staging -l app=backend \
  -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n meeting-automation-staging "$BACKEND_POD" -- python -c "
import boto3
s3 = boto3.client('s3', endpoint_url='http://minio-staging:9000',
  aws_access_key_id='minio_user_staging',
  aws_secret_access_key='minio_password_staging_2026')
try:
    s3.create_bucket(Bucket='meeting-recordings-staging')
    print('Bucket erstellt')
except: print('Bucket bereits vorhanden')
"
```

### Schritt 12: Users seeden
```bash
BACKEND_POD=$(kubectl get pods -n meeting-automation-staging -l app=backend \
  -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n meeting-automation-staging "$BACKEND_POD" -- \
  bash -c "cd /app && python scripts/seed_users.py"
```

### Schritt 13: Health Check
```bash
BACKEND_POD=$(kubectl get pods -n meeting-automation-staging -l app=backend \
  -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n meeting-automation-staging "$BACKEND_POD" -- \
  curl -s http://localhost:8000/health
# Erwartet: {"status":"healthy","version":"1.0.0"}
```

### Schritt 14: E2E Test Files kopieren
```bash
for POD in $(kubectl get pods -n meeting-automation-staging -l app=backend \
  -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}'); do
  kubectl cp backend/tests/conftest.py meeting-automation-staging/${POD}:/app/tests/conftest.py
  kubectl cp backend/tests/e2e/conftest.py meeting-automation-staging/${POD}:/app/tests/e2e/conftest.py
  for f in backend/tests/e2e/test_*.py; do
    kubectl cp "$f" meeting-automation-staging/${POD}:/app/tests/e2e/$(basename $f)
  done
  kubectl exec -n meeting-automation-staging "$POD" -- pip install -q pytest-rerunfailures==13.0
done
```

---

## Zugriff auf das Staging Frontend

```bash
kubectl port-forward svc/frontend 3001:80 \
  -n meeting-automation-staging \
  --kubeconfig /home/opc/meeting-automation/kubeconfig-staging.txt
```
→ http://localhost:3001

| User | Email | Passwort | Rolle |
|------|-------|---------|-------|
| Admin | admin@meeting.tn | Password123! | system_admin |
| Tech | tech@meeting.tn | Password123! | tech_admin |
| DG | dg@meeting.tn | Password123! | dg |
| Manager | manager@meeting.tn | Password123! | manager |
| User | user@meeting.tn | Password123! | participant |

---

## Datenpersistenz

| Komponente | Storage | Host-Pfad | Verhalten bei Cluster-Löschung |
|-----------|---------|-----------|-------------------------------|
| PostgreSQL | hostPath `/data/postgres` | `/home/opc/meeting-automation/data/postgres` | **Daten bleiben erhalten** |
| MinIO | hostPath `/data/minio` | `/home/opc/meeting-automation/data/minio` | **Daten bleiben erhalten** |
| Redis | EmptyDir / ephemeral | — | Daten verloren (Cache — OK) |
| RabbitMQ | volumeClaimTemplate | Kind PVC (ephemeral) | Daten verloren (Queue — OK) |

**Wichtig:** Bei `kind delete cluster --name meeting-staging` bleiben PostgreSQL und MinIO Daten auf dem Host erhalten. Beim nächsten Cluster-Start werden sie automatisch wieder gemountet (via `kind-config-staging.yaml`).

---

## Wichtige Dateien

| Datei | Zweck |
|-------|-------|
| `kind-config-staging.yaml` | Kind Cluster Config mit extraMounts + extraPortMappings |
| `kubeconfig-staging.txt` | Kubeconfig für meeting-staging Cluster |
| `infrastructure/kubernetes/staging/postgres-statefulset.yaml` | hostPath Storage |
| `infrastructure/kubernetes/staging/minio-statefulset.yaml` | hostPath Storage |
| `infrastructure/kubernetes/staging/traefik-ingressroute-local.yaml` | HTTP-only IngressRoute |
| `infrastructure/kubernetes/staging/frontend-deployment.yaml` | Frontend Deployment |
| `data/postgres/` | PostgreSQL Daten (persistent) |
| `data/minio/` | MinIO Daten (persistent) |
