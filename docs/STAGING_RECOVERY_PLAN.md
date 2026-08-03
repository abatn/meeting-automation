# Staging Cluster — Recovery & Rekonstruktionsplan

> **Aktualisiert**: 2026-06-24 | k3s Migration abgeschlossen, n8n workflows importiert

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
│       ├── n8n-staging (Deployment, NodePort 31678)
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

### Problem 8: Docker Multi-Arch Build — QEMU fehlt (CI/CD) — 2026-08-01

**Symptom:** Docker Hub `:latest` für `batnini/meeting-automation-backend` und `batnini/meeting-automation-frontend` hat NUR `arm64` + Attestation-Manifest. Contabo Produktion (AMD64/x86_64) kann `:latest` nicht pullen → `ImagePullBackOff` (`no match for platform`).

**Ursache:** `.github/workflows/docker-build.yml` fehlt `docker/setup-qemu-action@v3` vor `docker/setup-buildx-action@v3`. Ohne QEMU kann der GitHub Actions Runner (AMD64) nicht für ARM64 cross-compilieren. Die `platforms: linux/amd64,linux/arm64` Konfiguration schlägt bei arm64 fehl — Buildx überspringt fehlgeschlagene Plattformen SILENTLY (kein Fehler, Run zeigt "success").

**Beweis (2026-08-01):**
- `grep -c 'qemu' .github/workflows/docker-build.yml` → `0` (exit code 1)
- `docker manifest inspect batnini/meeting-automation-backend:latest` → arm64 + unknown/unknown (attestation), KEIN amd64
- `docker manifest inspect batnini/meeting-automation-frontend:latest` → gleiches Ergebnis
- GitHub Actions Buildx Builder Plattformen: `linux/amd64, linux/amd64/v2, linux/amd64/v3, linux/amd64/v4, linux/386` — KEIN arm64
- Alle 5 letzten Runs zeigen `completed/success` — trotzdem falsche Images
- k3s Staging: `imagePullPolicy: Always` → pullt von Docker Hub → arm64 passt (OCI = ARM64)
- k3s Produktion: `imagePullPolicy: Always` → pullt von Docker Hub → arm64 passt NICHT (Contabo = AMD64)

**Kontext aus `.loop.md`:**
- Phase 163 C10: "DiskPressure evicted Pods + GC'd unser `:latest` Image aus dem k3s-Store"
- Phase 163 K2: "`imagePullPolicy: Always` + lokale Images = ImagePullBackOff → `IfNotPresent`"
- Staging (OCI) funktioniert weil ARM64 + arm64-Image = Match
- Produktion (Contabo) ist kaputt weil AMD64 + arm64-Image = Mismatch

**Lösung (Commit `ce509141`):**

In `.github/workflows/docker-build.yml`, zwischen Checkout und Buildx einfügen:
```yaml
    - name: Set up QEMU
      uses: docker/setup-qemu-action@v3
```

Danach:
- amd64: Nativ auf GitHub Actions Runner gebaut
- arm64: Via QEMU emuliert
- Docker Hub `:latest` hat BEIDE Plattformen
- Contabo (AMD64) kann pullen → kein ImagePullBackOff

**Änderung:** 1 Datei, 3 Zeilen hinzugefügt
| Datei | Änderung |
|-------|----------|
| `.github/workflows/docker-build.yml` | `docker/setup-qemu-action@v3` vor `docker/setup-buildx-action@v3` |

**Verifikation:**
- GitHub Actions Workflow getriggert (push + workflow_dispatch) — Run `30713556529` + `30713565150`
- Nach Build: `docker manifest inspect` prüfen ob amd64 + arm64 vorhanden
- Contabo Pods: automatischer Pull bei `imagePullPolicy: Always`

**HARTE LESSONS:**
| # | Regel |
|---|-------|
| D1 | **QEMU MUSS VOR Buildx registriert werden** — `docker/setup-buildx-action@v3` erstellt Builder nur mit Host-Plattform. Ohne QEMU keine Cross-Compilation. |
| D2 | **Buildx überspringt fehlgeschlagene Plattformen SILENTLY** — Run zeigt "success" trotz fehlender Plattform. Immer `docker manifest inspect` nach dem Build prüfen. |
| D3 | **`imagePullPolicy: Always` + Docker Hub = Single-Source-of-Truth** — Wenn Docker Hub nur arm64 hat, sind alle AMD64-Cluster kaputt. Multi-arch ist Pflicht. |
| D4 | **Lokale Builds überschreiben CI-Builds** — Images die lokal auf dem ARM64-Staging-Server gebaut und gepusht wurden, haben `:latest` überschrieben. Immer über CI pushen. |

---

### Problem 9: cnpg-policy NetworkPolicy blockiert PRO Worker DB-Zugriff — 2026-08-01

**Symptom:** Test-Meeting "test test" blieb bei `Recording: uploaded` stecken. Pipeline (Transkription → PV → Actions) wurde nie gestartet. Recording-Datei existierte in MinIO, aber `process_recording` Celery-Task wurde nie ausgeführt.

**Ursache:** `cnpg-policy` NetworkPolicy erlaubte `celery-worker-pro-staging` UND `celery-beat-staging` keinen Zugriff auf CNPG PostgreSQL (Port 5432). Zusammen mit `default-deny-all` wurde jeder Traffic blockiert, der nicht explizit erlaubt war. Der GRATUIT Worker (`celery-worker-staging`) funktionierte weil er in der Policy stand. PRO Worker und Celery-Beat fehlten.

**Beweis (2026-08-01):**
- LiveKit Server sendete `egress_ended` Webhook an Backend ✅
- Backend empfing Webhook und dispatchte `process_recording.apply_async()` ✅
- Redis Dedup Key existierte (Wert=1) — Webhook wurde verarbeitet ✅
- PRO Worker empfing Task (`process_recording[eb0ceab8...] received`) ✅
- PRO Worker konnte DB NICHT erreichen (`pg_isready: no response`) ❌
- GRATUIT Worker konnte DB erreichen (`pg_isready: accepting connections`) ✅
- Celery-Beat konnte DB NICHT erreichen (`pg_isready: no response`) ❌
- `cnpg-policy` hatte `celery-worker-staging` aber NICHT `celery-worker-pro-staging` ❌
- `cnpg-policy` hatte NICHT `celery-beat-staging` ❌

**Root Cause Chain:**
```
default-deny-all NetworkPolicy
    ↓
cnpg-policy erlaubt 5432 nur für: backend, n8n, celery-worker-staging
    ↓
celery-worker-pro-staging UND celery-beat-staging fehlen
    ↓
PRO Worker → 10.43.52.37:5432 = BLOCKIERT
    ↓
Celery-Beat → 10.43.52.37:5432 = BLOCKIERT
    ↓
process_recording Task kann DB nicht erreichen
    ↓
Recording bleibt "uploaded"
    ↓
Keine Transkription, kein PV, keine Actions
    ↓
Periodic Tasks (check_storage_quotas, daily_reminder) fehlgeschlagen
```

**Lösung (Live + Repo):**

Live-Cluster (kubectl patch — 2 Patches):
```bash
# Fix 1: celery-worker-pro-staging
kubectl patch networkpolicy cnpg-policy -n meeting-automation-staging \
  --type='json' \
  -p='[{"op":"add","path":"/spec/ingress/0/from/-","value":{"podSelector":{"matchLabels":{"app":"celery-worker-pro-staging"}}}}]'

# Fix 2: celery-beat-staging
kubectl patch networkpolicy cnpg-policy -n meeting-automation-staging \
  --type='json' \
  -p='[{"op":"add","path":"/spec/ingress/0/from/-","value":{"podSelector":{"matchLabels":{"app":"celery-beat-staging"}}}}]'
```

Repo-Datei (`infrastructure/kubernetes/staging/network-policies.yaml`):
```yaml
# cnpg-policy: Neue podSelector
    - podSelector:
        matchLabels:
          app: celery-worker-pro-staging
    - podSelector:
        matchLabels:
          app: celery-beat-staging
```

**Änderung:** 1 Datei (Repo) + 2 kubectl patches (Live)
| Datei | Änderung |
|-------|----------|
| `infrastructure/kubernetes/staging/network-policies.yaml` | `app: celery-worker-pro-staging` + `app: celery-beat-staging` zu cnpg-policy hinzugefügt |
| Live Cluster | 2x kubectl patch auf cnpg-policy |

**Verifikation:**
- `pg_isready` von PRO Worker → `accepting connections` ✅
- `pg_isready` von Celery-Beat → `accepting connections` ✅
- `process_recording` Task manuell gestartet → Recording Status wechselte zu `completed` ✅
- Transkription: `completed` ✅
- PV: `draft` (wird generiert)
- Meeting: `COMPLETED` ✅

**HARTE LESSONS:**
| # | Regel |
|---|-------|
| N1 | **Jeder Pod der DB braucht MUSS in `cnpg-policy` stehen** — `default-deny-all` blockiert alles was nicht explizit erlaubt ist. Bei neuen Deployments (z.B. `celery-worker-pro-staging`) IMMER prüfen ob alle NetworkPolicies aktualisiert werden müssen. |
| N2 | **Celery Workers brauchen DB-Zugriff für `process_recording`** — Ohne DB-Verbindung kann der Task den Recording-Status nicht aktualisieren und die Pipeline nicht starten. |
| N3 | **`postgres-policy` ≠ `cnpg-policy`** — `postgres-policy` trifft den alten Pod `app: postgres-staging` (existiert nicht mehr). `cnpg-policy` trifft den aktuellen CNPG-Pod `app.kubernetes.io/name: postgresql`. Nur `cnpg-policy` ist relevant. |
| N4 | **Celery-Beat braucht ebenfalls DB-Zugriff** — `check_storage_quotas`, `daily_reminder_task` und `cleanup_old_data_task` lesen/quottieren Daten aus der DB. `celery-beat-staging` fehlte ebenfalls in `cnpg-policy` und wurde im selben Fix behoben. |
| N5 | **Webhook-Dedup (Redis SETNX) verhindert Duplikate** — Wenn der Webhook bereits empfangen wurde (Dedup Key=1), wird er nicht erneut verarbeitet. Bei Pipeline-Fehlern muss der Task manuell neu gestartet werden. |

---

### Problem 10: K8s TLS Zertifikat fehlt öffentliche IP (OCI Staging) — 2026-08-02

**Symptom:** E2E-Tests schlagen fehl mit: `tls: failed to verify certificate: x509: certificate is valid for 10.0.0.191, 10.43.0.1, 127.0.0.1, ::1, not 158.180.18.110`

**Ursache:** k3s API-Server Zertifikat wurde generiert OHNE die öffentliche IP `158.180.18.110` in den Subject Alternative Names (SANs). Die CI/CD Pipeline (GitHub Actions) verbindet sich via `KUBE_CONFIG_STAGING` Secret mit `https://158.180.18.110:6443`, aber das Zertifikat kennt diese IP nicht.

**Beweis (2026-08-02):**
```bash
# OpenSSL Zertifikat-Check:
$ echo | openssl s_client -connect 158.180.18.110:6443 2>/dev/null | openssl x509 -noout -text
X509v3 Subject Alternative Name:
    DNS: instance-20260329-0846
    IP: 10.0.0.191, 10.43.0.1, 127.0.0.1, 0:0:0:0:0:0:0:1
# 158.180.18.110 FEHLT!
```

**Vergleich mit Produktion (Contabo):**
```bash
# Produktion — KORREKT:
$ echo | openssl s_client -connect 169.58.83.32:6443 2>/dev/null | openssl x509 -noout -text
X509v3 Subject Alternative Name:
    DNS: contabo-prod, DNS: meeting-automation.com
    IP: 169.58.83.32, 10.43.0.1, 127.0.0.1
# 169.58.83.32 ENTHALTEN ✅
```

**Impact:**
- ❌ Alle E2E-Deployments (Staging) schlagen fehl (seit 2026-08-01)
- ✅ Frontend CI (Lint + Type-Check + Build) funktioniert weiterhin
- ✅ Production Deploy ist nicht betroffen (anderer kubeconfig)

**Lösung (manuell auf OCI Staging Server):**
```bash
# 1. SSH auf OCI Staging
ssh opc@158.180.18.110

# 2. k3s stoppen
sudo systemctl stop k3s

# 3. Alte Zertifikate löschen
sudo rm -rf /var/lib/rancher/k3s/server/tls/

# 4. k3s config.yaml mit tls-san erstellen
sudo mkdir -p /etc/rancher/k3s
sudo tee /etc/rancher/k3s/config.yaml <<EOF
tls-san:
  - 158.180.18.110
  - kubernetes
  - kubernetes.default
  - kubernetes.default.svc
  - kubernetes.default.svc.cluster.local
  - localhost
  - 127.0.0.1
  - 10.43.0.1
EOF

# 5. k3s neu starten
sudo systemctl daemon-reload
sudo systemctl start k3s

# 6. Verifizieren
sudo kubectl get nodes
openssl s_client -connect 158.180.18.110:6443 2>/dev/null | openssl x509 -noout -text | grep -A1 "Subject Alternative"

# 7. Neues kubeconfig exportieren
sudo cat /etc/rancher/k3s/k3s.yaml | sed "s/127.0.0.1/158.180.18.110/g" > /tmp/kubeconfig-staging-new.yaml
cat /tmp/kubeconfig-staging-new.yaml
```

**Nach der Reparatur:**
1. GitHub Secret `KUBE_CONFIG_STAGING` mit neuem kubeconfig aktualisieren
2. E2E-Pipeline neu triggern (workflow_dispatch)

**Änderung:** 0 Dateien (Infra-Fix, kein Code)

**HARTE LESSONS:**
| # | Regel |
|---|-------|
| T1 | **k3s `--tls-san` MUSS bei der ersten Installation gesetzt werden** — Ohne `tls-san` generiert k3s Zertifikate nur mit internen IPs. Öffentliche IPs müssen explizit via `config.yaml` oder `--tls-san` Flag angegeben werden. |
| T2 | **Produktion wurde korrekt konfiguriert** — Contabo (`169.58.83.32`) hat die öffentliche IP im Zertifikat. OCI Staging wurde ohne `--tls-san` gestartet. |
| T3 | **E2E-Tests testen NICHT den Code, sondern die Infra** — Wenn der E2E-Deploy-Step fehlschlägt, liegt es oft an Infra-Problemen (NetworkPolicy, TLS, Secrets), nicht am Code. |
| T4 | **`openssl s_client` ist der beste TLS-Diagnostic-Tool** — `openssl s_client -connect IP:6443 | openssl x509 -noout -text | grep SAN` zeigt sofort ob eine IP im Zertifikat fehlt. |

---

### Problem 11: CronJob Namespace-Mismatch in CI/CD Pipeline — 2026-08-02

**Symptom:** E2E-Pipeline `deploy-staging-and-test` scheiterte mit:
```
Error: the namespace from the provided object "kube-system" does not match
the namespace "meeting-automation-staging"
```

**Root Cause:** CronJob-Dateien (`ephemeral-storage-cleanup`, `pod-garbage-collector`, `longhorn-cleanup`) mit hardcoded `namespace: kube-system` lagen in `infrastructure/kubernetes/staging/`. CI/CD `kubectl apply -f .../staging/ -n meeting-automation-staging` wandte ALLE Dateien mit `-n meeting-automation-staging` an → Namespace-Konflikt.

**Fix:** CronJob-Dateien nach `infrastructure/kubernetes/system/` verschoben + separater CI/CD-Step in `e2e-tests.yml`.

**Änderung:** `.github/workflows/e2e-tests.yml` (neuer Step "Deploy System CronJobs")

---

### Problem 12: Longhorn nicht installiert auf OCI Staging — 2026-08-02

**Symptom:** `longhorn-cleanup` CronJob scheiterte mit `namespaces "longhorn-system" not found`.

**Root Cause:** Longhorn war nie auf OCI Staging installiert. Alle 5 letzten Pipeline-Runs fehlgeschlagen.

**Fix:** Longhorn v1.12.0 via Helm installiert (`createDefaultDiskLabeledNodes=true`, `defaultReplicaCount=1`, `defaultClass=false`). 8 HARTE LESSONS (LH1-LH8) dokumentiert in `.loop.md` Phase 188.

**Änderung:** `.loop.md` (Dokumentation) + `infrastructure/kubernetes/staging/longhorn-setup.sh` (Setup-Script)

---

### Problem 13: Metrics-Server auf OCI Staging funktionierte nicht — 2026-08-02

**Symptom:** `kubectl top nodes` → `error: Metrics API not available`. APIService in Phase 188 gelöscht (um Namespace-Deletion zu entblocken).

**Root Cause:** OCI VNIC Security List blockiert Pod→Node Traffic auf Port 10250. `hostNetwork=true` + Port 4443 (nicht 10250, belegt von kubelet) + EndpointSlice + APIService-Recreation.

**Fix:** `metrics-server-patch.yaml` in Git + 5 HARTE LESSONS (MS1-MS5) in `.loop.md` Phase 189.

**Änderung:** `infrastructure/kubernetes/staging/metrics-server-patch.yaml` (NEU) + `.loop.md`

---

### Problem 14: Dual Default StorageClass auf OCI Staging — 2026-08-03

**Symptom:** `local-path` und `longhorn` hatten beide `storageclass.kubernetes.io/is-default-class=true`. PVCs ohne explizite `storageClassName` → Ambiguität.

**Root Cause:** Helm-Chart `defaultClass=true` setzt eigene Default, entfernt nicht existierende Defaults.

**Fix:** `kubectl patch storageclass local-path -p '{"metadata":{"annotations":{"storageclass.kubernetes.io/is-default-class":"false"}}}'`. Longhorn-Helm-Befehl in `.loop.md` Phase 188 auf `defaultClass=false` aktualisiert. 2 HARTE LESSONS (SC1-SC2) in `.loop.md` Phase 189a.

**Änderung:** `.loop.md` (Dokumentation)

---

## Zusammenfassung Phase 187-189a (2026-08-02/03)

| Phase | Problem | Lösung | Status |
|-------|---------|--------|--------|
| 187 | CronJob Namespace-Mismatch | CronJobs nach `system/` verschoben | ✅ IMPLEMENTIERT |
| 188 | Longhorn nicht installiert | Helm v1.12.0 + 8 HARTE LESSONS | ✅ IMPLEMENTIERT |
| 189 | Metrics-Server kaputt | hostNetwork + Port 4443 + EndpointSlice | ✅ IMPLEMENTIERT |
| 189a | Dual Default StorageClass | `local-path` Default entfernt | ✅ IMPLEMENTIERT |

**Pipeline-Ergebnis (Run 30771585262):**
| Job | Status |
|-----|--------|
| `build-and-test-dev` | ✅ success (291+ E2E Tests) |
| `deploy-staging-and-test` | ✅ success |
| `deploy-production` | ❌ failure (`longhorn-system` Namespace fehlt auf Contabo) |

**Commits:**
| Hash | Beschreibung |
|------|-------------|
| `8587c7f1` | fix(ci): CronJob Namespace-Mismatch in e2e-tests.yml |
| `380c9644` | docs: add Phase 188 — Longhorn repair on OCI Staging |
| `38607fa2` | docs: add Phase 189 — metrics-server repair |
| `e5a4c23f` | fix(k8s): add metrics-server-patch.yaml |
| `7d1d0bf7` | docs: add Phase 189a — fix dual default StorageClass |
| `2df83b6e` | docs: update Phase 188 Helm command — defaultClass=false |
| `8117092d` | feat(k8s): add longhorn-setup.sh |

**Noch offen:**
| # | Problem | Nächster Schritt |
|---|---------|-----------------|
| 1 | ~~Production hat kein `longhorn-system` Namespace~~ | ✅ GELÖST — Pipeline prüft ob `longhorn-system` existiert, skippt graceful wenn nicht (Commit `c568651e` + `09880019`) |
| 2 | ~~Hardcoded Node-IP `10.0.0.191` in EndpointSlice~~ | ✅ GELÖST — `apply-metrics-endpointslice.sh` erkennt Node-IP dynamisch via `kubectl get nodes` |
| 3 | ~~Metrics-Server Patch live-only (nicht in Git)~~ | ✅ GELÖST — `metrics-server-patch.yaml` + `apply-metrics-endpointslice.sh` + `longhorn-setup.sh` in Git |

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
| `infrastructure/kubernetes/staging/n8n-service-nodeport.yaml` | n8n NodePort 31678 (Phase 47) |
| `infrastructure/kubernetes/staging/n8n-nodeport-policy.yaml` | ISO 27001 A.8.20 compliant NetworkPolicy (Phase 47) |
| `data/postgres/` | PostgreSQL Daten (persistent) |
| `data/minio/` | MinIO Daten (persistent) |
