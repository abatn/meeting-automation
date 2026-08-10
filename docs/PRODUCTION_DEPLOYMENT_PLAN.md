# 🚀 Production Deployment Plan: Meeting Automation System

> **Staging Status (2026-07-29)**: k3s v1.35.5+k3s1 auf OCI VM (158.180.18.110), Pipeline funktional ✅, n8n 7 Workflows aktiv ✅, cert-manager v1.20.2 + nginx-ingress installiert (Phase 53)
> **Production Status (2026-07-29)**: k3s v1.36.2+k3s1 auf Contabo VPS (169.58.83.32), 10/10 Deployments Ready ✅, Docker deaktiviert ✅, deploy-production.yml via SSH funktioniert ✅

**Stand:** 2026-04-03 (aktualisiert 2026-07-29)
**Status:** Test abgeschlossen (53/53 E2E-Tests passed ✅), Production Recovery abgeschlossen (Steps 1-7)
**Ziel:** Deployment von Test → Staging → Production

---

## 🎯 Aktueller Stand (2026-07-29)

### Production Infrastructure
| Komponente | Status | Details |
|------------|--------|---------|
| **Server** | ✅ | Contabo VPS, 169.58.83.32, 290 GiB Disk, 74 GiB frei |
| **k3s** | ✅ | v1.36.2+k3s1, single-node, namespace `meeting-automation` |
| **Docker** | ✅ | Deaktiviert (`systemctl disable docker`) — kein Doppelter Speicherverbrauch |
| **Deploy-Pipeline** | ✅ | `deploy-production.yml` via SSH → Contabo → k3s (funktioniert) |
| **E2E Pipeline** | ⚠️ | `deploy-production` Job in `e2e-tests.yml` (DEPRECATED — renamed to `e2e-tests.yml.disabled`, replaced by `ci.yml`) braucht `KUBE_CONFIG_PRODUCTION` Secret-Update |

### Bekannte Probleme & Fixes

| Problem | Status | Lösung |
|---------|--------|--------|
| Docker + k3s parallel (40 GiB Müll) | ✅ Gelöst | Docker deaktiviert, 40 GiB freigeräumt |
| celery-worker-pro OOMKill (53 Restarts) | ✅ Gelöst | 5 NetworkPolicies gepatcht |
| Stale :latest Image (containerd Cache) | ✅ Gelöst | `k3s ctr images rm` vor Pull in Pipeline |
| E2E Test Login 401 (db_session Email) | ✅ Gelöst | `conftest.py` — `db_session` nutzt `E2E_TEST_USER_EMAIL` env var |
| Phase79 timing bug (ck_meeting_end_after_start) | ✅ Gelöst | `end_time=datetime.utcnow() + timedelta(hours=1)` |
| KUBE_CONFIG_PRODUCTION `127.0.0.1:6443` | ✅ Gelöst | Secret-Update mit korrekter IP (`169.58.83.32:6443`) |
| **Production TLS fehlt komplett** | 🔴 Offen | Siehe Abschnitt **§10: Production TLS/cert-manager Plan** unten — identisch zum erfolgreichen Staging-Fix (Phase 183) |

### Sofort-Maßnahmen (nächster Schritt)
```bash
# 1. KUBE_CONFIG_PRODUCTION Secret aktualisieren
gh secret set KUBE_CONFIG_PRODUCTION --body "$(cat ~/.kube/config-prod)"

# 2. Deploy triggern (Option A: manuell)
gh workflow run deploy-production.yml

# Oder (Option B: automatisch via Push)
git commit --allow-empty -m "trigger deploy: update KUBE_CONFIG_PRODUCTION"
git push
```

---

## 📊 1. Infrastruktur-Matrix: Test vs Staging vs Production

| Komponente | Test (docker-compose.e2e.yml) | Local Dev (docker-compose.yml) | Staging (K8s Namespace) | Production (K8s Namespace) |
|------------|------------------------------|-------------------------------|-------------------------|---------------------------|
| **Orchestration** | Docker Compose | Docker Compose | Kubernetes | Kubernetes |
| **Namespace** | N/A (bridge network) | N/A | `meeting-automation-staging` | `meeting-automation` |
| **Database** | PostgreSQL Port 5433 | PostgreSQL Port 5432 | StatefulSet ClusterIP | StatefulSet ClusterIP |
| **DB Name** | `meeting_db_test` | `meeting_db` | `meeting_db_staging` | `meeting_db` |
| **Redis** | Port 6380 | Port 6379 | ClusterIP: 6379 | ClusterIP: 6379 |
| **RabbitMQ** | Ports 5673/15673 | Ports 5672/15672 | ClusterIP: 5672/15672 | ClusterIP: 5672/15672 |
| **MinIO** | Ports 9002/9003 | Ports 9000/9001 | ClusterIP: 9000/9001 | ClusterIP: 9000/9001 |
| **n8n** | Port 5679 | Port 5678 | ClusterIP: 5678 + NodePort 31678 (UI) | ClusterIP: 5678 |
| **OnlyOffice** | Port 8081, test secret | Port 8080, .env secret | ClusterIP: 8080 | ClusterIP: 8080 |
| **Backend** | Port 8001, test env | Port 8000, .env | 2 Replicas, 1Gi RAM | 3 Replicas, 2Gi RAM |
| **Frontend** | Nicht vorhanden | Port 3000 | 2 Replicas, Nginx | 3 Replicas, Nginx |
| **Celery Worker** | Nicht vorhanden | 2G RAM, bg process | 1 Replica, 512Mi | 3 Replicas, 2Gi |
| **Celery Beat** | Nicht vorhanden | 512M RAM | 1 Replica | 1 Replica (mit leader election) |
| **Ingress** | Lokal: Ports | Kein Ingress | nginx-ingress NodePort 30080/30443 | nginx-ingress LoadBalancer |
| **Domain** | localhost | localhost | staging.meeting-automation.com | meeting-automation.com |
| **TLS** | Self-signed (localhost) | Kein TLS | cert-manager v1.20.2 + Let's Encrypt HTTP-01 (Phase 53) | Let's Encrypt (Production) |
| **Network Policies** | Keine | Keine | 14 Policies (default-deny + allow-regeln + NodePort + nginx-ingress) | 13+ Policies (default-deny + allow-regeln) |
| **Resource Limits** | Nein | Ja (deploy.resources) | ✅ Ja | ✅ Ja (höher) |
| **Secrets** | .env (klartext) | .env (klartext) | SOPS-verschlüsselte K8s Secrets | SOPS-verschlüsselte K8s Secrets |
| **Monitoring** | Manuell | Manuell | Custom Dashboard + Prometheus optional | Custom Dashboard + Prometheus + Alertmanager |
| **Backup** | Keine | Keine | Täglich pg_dump → MinIO | Täglich pg_dump + WAL → Offsite S3 |
| **CI/CD** | Lokal | Lokal | GitHub Actions → Staging Auto | GitHub Actions → Production Manual Approval (`deploy-production.yml` via SSH) |

---

## 🔐 2. Secrets-Mapping-Tabelle

### 2.1 Production Secrets Übersicht

| Secret File | Zweck | Enthält |
|-------------|-------|---------|
| `backend-secrets.yaml` | Backend API Credentials | DATABASE_URL, SECRET_KEY, API-Keys, SMTP, JWT, Celery URLs |
| `postgres-secrets.yaml` | DB Credentials | POSTGRES_USER, POSTGRES_PASSWORD |
| `redis-secrets.yaml` | Redis Auth | REDIS_PASSWORD |
| `rabbitmq-secrets.yaml` | Message Broker | RABBITMQ_DEFAULT_USER/PASS, ERLANG_COOKIE |
| `minio-secrets.yaml` | Object Storage | MINIO_ROOT_USER/PASSWORD |
| `n8n-secrets.yaml` | n8n DB Access + API Key | DB_USER/PASSWORD, N8N_API_KEY |
| `traefik-tls-secret.yaml` | HTTPS Zertifikat | TLS cert/key (Let's Encrypt) |

### 2.2 Mapping: .env Variable → K8s Secret

| .env Variable | K8s Secret | Key Name | Typ | Production-Wertquelle |
|---------------|------------|----------|-----|----------------------|
| `DATABASE_URL` | `backend-secrets` | `DATABASE_URL` | Opaque | `postgresql+asyncpg://meeting_user:${password}@postgres:5432/meeting_db_prod` |
| `REDIS_URL` | `backend-secrets` | `REDIS_URL` | Opaque | `redis://:${password}@redis:6379/0` |
| `SECRET_KEY` | `backend-secrets` | `SECRET_KEY` | Opaque | `openssl rand -hex 32` |
| `MISTRAL_API_KEY` | `backend-secrets` | `MISTRAL_API_KEY` | Opaque | **Neuer Production-Key** von Mistral AI |
| `OPENAI_API_KEY` | `backend-secrets` | `OPENAI_API_KEY` | Opaque | Falls genutzt – Production-Key |
| `GLADIA_API_KEY` | `backend-secrets` | `GLADIA_API_KEY` | Opaque | **Neuer Production-Key** von Gladia |
| `SMTP_HOST` | `backend-config` | `SMTP_HOST` | ConfigMap | `smtp.sendgrid.net` (oder SES) |
| `SMTP_PORT` | `backend-config` | `SMTP_PORT` | ConfigMap | `587` |
| `SMTP_USER` | `backend-config` | `SMTP_USER` | ConfigMap | `apikey` (SendGrid) |
| `SMTP_PASSWORD` | `backend-secrets` | `SMTP_PASSWORD` | Opaque | **SendGrid/SES API Key** |
| `S3_ACCESS_KEY` | `backend-secrets` | `S3_ACCESS_KEY` | Opaque | MinIO oder S3 Credential |
| `S3_SECRET_KEY` | `backend-secrets` | `S3_SECRET_KEY` | Opaque | MinIO oder S3 Credential |
| `S3_ENDPOINT` | `backend-config` | `S3_ENDPOINT` | ConfigMap | `http://minio:9000` (intern) |
| `S3_BUCKET_NAME` | `backend-config` | `S3_BUCKET_NAME` | ConfigMap | `meeting-recordings` |
| `ONLYOFFICE_SECRET` | `backend-secrets` | `ONLYOFFICE_SECRET` | Opaque | **Neues starkes JWT Secret** |
| `ONLYOFFICE_URL` | `backend-config` | `ONLYOFFICE_URL` | ConfigMap | `http://onlyoffice:8080` |
| `N8N_WEBHOOK_URL` | `backend-config` | `N8N_WEBHOOK_URL` | ConfigMap | `http://n8n:5678/webhook` |
| `CELERY_BROKER_URL` | `backend-secrets` | `CELERY_BROKER_URL` | Opaque | `amqp://${user}:${pass}@rabbitmq:5672/` |
| `CELERY_RESULT_BACKEND` | `backend-secrets` | `CELERY_RESULT_BACKEND` | Opaque | `redis://:${pass}@redis:6379/2` |
| `INTERNAL_API_SECRET` | `backend-secrets` | `INTERNAL_API_SECRET` | Opaque | `openssl rand -hex 32` |
| `WHATSAPP_TOKEN` | `backend-secrets` | `WHATSAPP_TOKEN` | Opaque | **WhatsApp Business Production Token** |
| `CORS_ORIGINS` | `backend-config` | `CORS_ORIGINS` | ConfigMap | `["https://meeting-automate.tn"]` |

### 2.3 Fehlende Secrets (müssen hinzugefügt werden!)

In `infrastructure/kubernetes/backend-secrets.yaml` fehlen:

- `ONLYOFFICE_SECRET`
- `WHATSAPP_TOKEN`
- `STRIPE_SECRET_KEY` (falls Stripe aktiv)
- `N8N_WEBHOOK_USER_INVITED` (falls separat von N8N_WEBHOOK_URL)

**Action:** `backend-secrets.yaml` erweitern um fehlende Keys, mit SOPS verschlüsseln.

---

## 🏢 3. Multi-Tenant Isolation & Audit-Logging in Production

### 3.1 Multi-Tenant Architecture (bereits implementiert)

✅ **JWT mit `client_id`**
- `app/core/security.py`: `create_access_token()` fügt `client_id` als Claim hinzu
- `app/middleware/audit_middleware.py`: Extrahiert `client_id` aus Token

✅ **Application-Level Row Filtering**
- Alle Services (`app/services/*`) filtern DB-Query nach `client_id`
- Beispiel `ReportService.get_dashboard_metrics()`:
  ```python
  query = query.filter(Meeting.client_id == current_user.client_id)
  ```

✅ **Network Policies (K8s)**
- `infrastructure/kubernetes/network-policies.yaml`:
  - `default-deny-all`: Blockiert alle Ingress/Egress
  - `allow-backend-to-database`: Nur Pods mit Labels `app: backend`, `app: n8n`, `app: celery-worker` dürfen auf Postgres Port 5432
  - `allow-frontend-ingress`: Erlaubt Traffic von überall zu Frontend (Port 80/443)
  - `allow-backend-to-redis`: Nur Backend/Celery zu Redis
  - `allow-backend-to-rabbitmq`: Nur Backend/Celery zu RabbitMQ

**Production-Checkliste:**
- ✅ Alle Backend-Pods laufen im Namespace `meeting-automation-prod`
- ✅ `backend-deployment.yaml` enthält `envFrom: secretRef/configMapRef`
- ✅ NetworkPolicy `meeting-automation` angewendet
- ✅ Traefik Rate Limiting für `/api/v1/auth` (5 req/s) und `/api/*` (50 req/s)

**Test nach Deployment:**
```bash
# Test: Tenant-Isolation (Integrationstest)
kubectl exec -it deployment/backend-prod -n meeting-automation-prod -- \
  curl -H "Authorization: Bearer $(token_tenant_A)" \
  https://meeting-automate.tn/api/v1/meetings
# → Darf nur Meetings von Tenant A sehen
```

---

### 3.2 Audit-Logging (ISO 27001)

✅ **AuditMiddleware** (`app/middleware/audit_middleware.py`):
- Loggt alle mutierenden Endpoints: POST/PUT/PATCH/DELETE
- Exception: `/recordings/upload` (Performance)
- Speichert: `user_id`, `client_id`, `action`, `resource_type`, `resource_id`, `ip_address`, `user_agent`, `old_values`, `new_values`

✅ **AuditLog Model** (`app/models/audit_log.py`):
- Tabelle mit Indizes: `created_at`, `client_id`, `user_id`, `action`
- Kein Delete (Soft-Delete nur für GDPR Compliance, aber Audit-Logs bleiben)

✅ **Admin API** (`app/api/v1/admin.py`):
- Endpoint: `GET /api/v1/admin/audit-logs`
- Filter: Zeitraum, Client, User, Action
- CSV Export

✅ **Test Coverage**: `tests/integration/test_audit_logging.py` vorhanden und passed ✅

**Production-Checkliste:**
- ✅ Tabelle `audit_logs` existiert (Alembic Migration)
- ✅ `AuditMiddleware` in FastAPI registriert (`app/main.py`)
- ✅ Backend-Config: `AUDIT_ENABLED="true"` (wenn konfigurierbar)
- ✅ Access zu `/admin/audit-logs` nur für `system_admin` und `tech_admin`

**Test nach Deployment:**
```bash
# Aktion durchführen (z.B. Meeting erstellen)
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -d '{"title":"Test"}' \
  https://meeting-automate.tn/api/v1/meetings

# Prüfen, ob Audit-Log geschrieben wurde
kubectl exec -it postgres-prod-0 -n meeting-automation-prod -- \
  psql -U meeting_user meeting_db_prod \
  -c "SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT 1;"
```

---

## 🛡️ 4. Backups, Monitoring & Alerting für Production

### 4.1 Backup-Strategie

⚠️ **Aktuell:** `scripts/backup-db.sh` ist TODO (leer).

#### Empfehlung: Tägliche Backups mit pg_dump + Offsite S3

**Backup-Plan:**

| Service | Backup-Typ | Frequenz | Retention | Offsite |
|---------|------------|----------|-----------|---------|
| PostgreSQL | Full dump (gzipped) | Täglich 2:00 UTC | 30 Tage | ✅ S3 (andere Region) |
| PostgreSQL | WAL Archiving | Kontinuierlich | 7 Tage | ✅ S3 |
| MinIO (S3) | Bucket Versioning | Aktiviert | Unbegrenzt | ✅ Replication zu Cloud S3 |
| Kubernetes Manifests | Git (bereits) | Bei jedem Commit | Permanent | ✅ GitHub |

**Implementation:**

1. **PostgreSQL CronJob** (in K8s):

```yaml
# infrastructure/kubernetes/backup-postgres-cronjob.yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: postgres-backup
  namespace: meeting-automation-prod
spec:
  schedule: "0 2 * * *"  # Täglich 2:00 UTC
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: pg-dump
            image: postgres:15-alpine
            command:
            - /bin/sh
            - -c
            - |
              DATE=$(date +%Y%m%d_%H%M%S)
              pg_dump -h postgres -U meeting_user meeting_db_prod | gzip > /backup/db_${DATE}.sql.gz

              # Upload zu S3 (MinIO extern S3)
              mc cp /backup/db_${DATE}.sql.gz myminio/meeting-automation-backups/postgres/

              # Alte Backups löschen (älter als 30 Tage)
              mc rm --older-than 30d myminio/meeting-automation-backups/postgres/
            env:
            - name: PGPASSWORD
              valueFrom:
                secretKeyRef:
                  name: postgres-secrets
                  key: POSTGRES_PASSWORD
            volumeMounts:
            - name: backup-volume
              mountPath: /backup
          restartPolicy: OnFailure
```

2. **WAL Archiving** (in `postgres-statefulset.yaml`):

```yaml
# In postgres StatefulSet container env:
- name: POSTGRESQL_EXTRA_OPTS
  value: "-c archive_mode=on -c archive_command='mc cp %p myminio/meeting-automation-backups/wal/%f'"
```

3. **MinIO Versioning** (manuell in MinIO UI oder API):
   ```bash
   mc version enable myminio/meeting-recordings
   ```

---

### 4.2 Monitoring Stack (Minimal Viable Product)

✅ **Bereits vorhanden:**
- Custom `monitoring_service.py` sammelt Metriken
- Endpoint: `GET /api/v1/admin/metrics` (nur für `tech_admin`)
- Frontend Dashboard: `admin/TechnikDashboard.tsx`

⚠️ **Fehlend für Production:**
- **Prometheus** für Metriken-Speicherung & Zeitreihen
- **Grafana** für Dashboards
- **Alertmanager** für Alerts

#### Option A: Minimal (ohne Prometheus)

**Backup für Custom Dashboard:**
- Metriken werden nur im RAM gehalten → bei Pod-Neustart verloren
- Keine Historie → kein Trend-Analyse

**Empfehlung:** Custom Dashboard ergänzen um Redis-Caching der Metriken (z.B. Redis Hash mit TTL 1h) → Backend kann historische Daten liefern. Aber immer noch kein Alerting.

---

#### Option B: Vollständig (Empfohlen)

**Stack:**
- Prometheus (scraped `/metrics` endpoint)
- Grafana (Dashboards)
- Alertmanager (Slack/Telegram Alerts)

**Implementation:**

1. **Backend Metriken Export** (Prometheus Format):

```python
# backend/app/services/metrics_service.py
from prometheus_client import Counter, Histogram, Gauge, generate_latest, REGISTRY
from fastapi import Response

# Metriken definieren
http_requests_total = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'status'])
http_request_duration = Histogram('http_request_duration_seconds', 'HTTP request latency')
db_connections_active = Gauge('db_connections_active', 'Active DB connections')
celery_queue_length = Gauge('celery_queue_length', 'Number of tasks in Celery queue')

@app.get("/metrics")
def metrics():
    return Response(generate_latest(REGISTRY), media_type="text/plain")
```

2. **Prometheus ConfigMap:**

```yaml
# infrastructure/kubernetes/prometheus-config.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: prometheus-config
  namespace: meeting-automation-prod
data:
  prometheus.yml: |
    global:
      scrape_interval: 15s
    scrape_configs:
      - job_name: 'backend'
        static_configs:
          - targets: ['backend.meeting-automation-prod.svc.cluster.local:8000']
        metrics_path: '/metrics'
      - job_name: 'postgres'
        static_configs:
          - targets: ['postgres-exporter.meeting-automation-prod.svc.cluster.local:9187']
      - job_name: 'redis'
        static_configs:
          - targets: ['redis-exporter.meeting-automation-prod.svc.cluster.local:9121']
```

3. **Deploy Prometheus via Helm:**

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --set prometheus.prometheusSpec.serviceMonitorSelectorNilUsesHelmValues=false \
  --set grafana.adminPassword='secure-grafana-password'
```

4. **Grafana Dashboards importieren:**
- Dashboard für Application Metrics (HTTP Requests, Error Rate, Latency)
- Dashboard für Database (Connections, Slow Queries, Cache Hit Ratio)
- Dashboard für AI Services (Gladia/Mistral Latency, Error Rate)
- Dashboard für Infrastructure (Pod CPU/Memory, Disk I/O)

5. **Alertmanager Rules:**

```yaml
# infrastructure/kubernetes/alert-rules.yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: meeting-automation-alerts
  namespace: meeting-automation-prod
spec:
  groups:
  - name: critical
    rules:
    - alert: PodNotRunning
      expr: up{namespace="meeting-automation-prod"} == 0
      for: 1m
      labels:
        severity: critical
      annotations:
        summary: "Pod {{ $labels.pod }} is down"
    - alert: HighErrorRate
      expr: rate(http_requests_total{status=~"5..",namespace="meeting-automation-prod"}[5m]) / rate(http_requests_total{namespace="meeting-automation-prod"}[5m]) > 0.05
      for: 2m
      labels:
        severity: warning
      annotations:
        summary: "High error rate: {{ $value }}"
    - alert: HighResponseLatency
      expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket{namespace="meeting-automation-prod"}[5m])) > 2
      for: 5m
      labels:
        severity: warning
      annotations:
        summary: "P95 latency > 2s: {{ $value }}s"
```

**Alerting Channel (Telegram Example):**

```yaml
# alertmanager-config.yaml
receivers:
- name: 'telegram'
  telegram_configs:
  - bot_token: '{{ .Values.telegramBotToken }}'
    chat_id: '{{ .Values.telegramChatId }}'
    parse_mode: 'HTML'
    text: |
      <b>{{ .CommonLabels.alertname }}</b><br/>
      {{ range .Alerts }}
      {{ .Annotations.summary }}<br/>
      {{ end }}
```

---

### 4.3 Logging (Centralized)

**Empfehlung:** Loki + Grafana für Log-Aggregation.

```bash
helm install loki grafana/loki-stack \
  --namespace monitoring \
  --set grafana.enabled=true \
  --set promtail.enabled=true
```

Logs aller Pods werden an Loki gesendet und sind durchsuchbar.

---

## 🚀 5. Deployment-Prozess: Test → Staging → Production

### 5.1 Übersicht (aktualisiert 2026-07-29)

```
Phase 1: Test (abgeschlossen ✅)
└─ docker-compose.e2e.yml → scripts/run-tests.sh
   └─ Ergebnis: 53/53 Tests passed

Phase 2: Build & Push (CI/CD) ✅
└─ GitHub Actions: docker-build.yml
   └─ Push Images zu Docker Hub (backend + frontend, :latest + :SHA)

Phase 3: Infrastruktur ✅ (manuell, nicht Terraform)
└─ Staging: OCI VM (158.180.18.110), k3s v1.35.5+k3s1
   └─ Production: Contabo VPS (169.58.83.32), k3s v1.36.2+k3s1

Phase 4: Staging Deployment ✅
└─ Namespace: meeting-automation-staging
   └─ E2E Pipeline deploy-staging-and-test (automatisch)

Phase 5: Staging Smoke Tests ✅
└─ E2E Pipeline: 28 Tests (automatisiert)
   └─ Bei Erfolg: Manual Approval für Production

Phase 6: Production Deployment ✅
└─ deploy-production.yml (standalone, SSH-basiert)
   └─ Namespace: meeting-automation
   └─ Image pull → k3s containerd → kubectl apply → rollout restart

Phase 7: Post-Deployment Validation ✅
└─ Smoke Tests in Pipeline + Health Check
```

---

### 5.2 Step-by-Step Runbook

#### Phase 1: Build Images (GitHub Actions – bereits konfiguriert)

```yaml
# .github/workflows/docker-build.yml
- name: Build and push backend
  uses: docker/build-push-action@v5
  with:
    context: ./backend
    file: ./backend/Dockerfile
    push: true
    tags: ${{ secrets.DOCKERHUB_USERNAME }}/meeting-automation-backend:${{ github.sha }}
```

✅ Images werden gepusht zu: `docker.io/<DOCKERHUB_USERNAME>/meeting-automation-backend:<SHA>`

---

#### Phase 2: Infrastructure Provisioning (Terraform)

**Datei:** `infrastructure/terraform/main.tf` (aktuell TODO – muss geschrieben werden!)

**Empfohlene Terraform Config für Hetzner (oder AWS/GCP):**

```hcl
# infrastructure/terraform/main.tf (Beispiel für Hetzner)
terraform {
  required_providers {
    hcloud = {
      source  = "hetznercloud/hcloud"
      version = "~> 1.38"
    }
  }
}

provider "hcloud" {
  token = var.hetzner_token
}

resource "hcloud_network" "meeting_automation" {
  name = "meeting-automation-network"
}

resource "hcloud_ssh_key" "default" {
  name       = "k8s-ssh-key"
  public_key = file(var.ssh_public_key_path)
}

resource "hcloud_k3s_cluster" "production" {
  name       = "meeting-automation-k3s"
  network_id = hcloud_network.meeting_automation.id

  # Server Nodes (Master)
  server {
    server_type = "cx21"
    labels = {
      "node-type" = "master"
    }
  }

  # Agent Nodes (Worker)
  agent {
    server_type = "cx31"
    labels = {
      "node-type" = "worker"
    }
    count = 3
  }
}

output "kubeconfig" {
  value = hcloud_k3s_cluster.production.kube_config
  sensitive = true
}
```

**Schritte:**
```bash
cd infrastructure/terraform
terraform init
terraform plan -var-file="production.tfvars"
terraform apply -var-file="production.tfvars"
```

➡️ Erzeugt K8s Cluster + `kubeconfig` für Production.

---

#### Phase 3: Prepare K8s Manifests für Production

**Vorbereitung:**

1. **Secrets updaten** mit Production-Werten:
   ```bash
   # 1. SOPS entschlüsseln, Werte ersetzen, wieder verschlüsseln
   sops --decrypt infrastructure/kubernetes/backend-secrets.yaml > backend-secrets-dec.yaml
   # Edit: MISTRAL_API_KEY, GLADIA_API_KEY, SMTP_PASSWORD, etc. durch Production ersetzen
   sops --encrypt backend-secrets-dec.yaml > infrastructure/kubernetes/backend-secrets.yaml
   ```

2. **ConfigMap updaten** (Domain, URLs):
   ```bash
   kubectl create configmap backend-config-prod \
     --from-literal=DEBUG="false" \
     --from-literal=CORS_ORIGINS='["https://meeting-automate.tn"]' \
     --from-literal=N8N_WEBHOOK_URL="http://n8n:5678/webhook" \
     --dry-run=client -o yaml > backend-config-prod.yaml
   ```

3. **Traefik TLS:** Let's Encrypt Zertifikat automatisch mit `cert-manager` holen:

```yaml
# infrastructure/kubernetes/cert-manager.yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: admin@meeting-automate.tn
    privateKeySecretRef:
      name: letsencrypt-prod-key
    solvers:
    - http01:
        ingress:
          class: traefik
```

---

#### Phase 4: Staging Deployment (Namespace staging)

```bash
# 1. Namespace erstellen
kubectl apply -f - <<EOF
apiVersion: v1
kind: Namespace
metadata:
  name: meeting-automation-staging
EOF

# 2. Secrets anpassen für Staging (Test-API-Keys)
kubectl apply -f infrastructure/kubernetes/ --namespace=meeting-automation-staging

# 3. DB für Staging: Neues DB-Instance oder gleiche DB mit suffix "_staging"?
# Empfehlung: Getrennte DB im selben PostgreSQL Cluster (neue DB)
kubectl exec -i statefulset/postgres -n meeting-automation-staging -- \
  psql -U meeting_user -c "CREATE DATABASE meeting_db_staging;"

# 4. Migration für Staging
kubectl exec -i deployment/backend -n meeting-automation-staging -- \
  bash -c "export PYTHONPATH=/app && alembic upgrade head"

# 5. Health Check
kubectl wait --for=condition=ready pod -l app=backend -n meeting-automation-staging --timeout=120s
```

---

#### Phase 5: Staging Smoke Tests

```bash
#!/bin/bash
# scripts/smoke-test-staging.sh

STAGING_URL="https://staging.meeting-automate.tn"

echo "🔍 Running Staging Smoke Tests..."

# 1. Backend Health
curl -f ${STAGING_URL}/health || { echo "❌ Backend health failed"; exit 1; }
echo "✅ Backend health OK"

# 2. Frontend lädt
curl -f ${STAGING_URL}/ | grep -q "Meeting Automation" || { echo "❌ Frontend failed"; exit 1; }
echo "✅ Frontend loads"

# 3. Admin Login (Testuser)
TOKEN=$(curl -X POST -H "Content-Type: application/json" \
  -d '{"email":"dg@meeting.tn","password":"testpass"}' \
  ${STAGING_URL}/api/v1/auth/login | jq -r '.access_token')
[ -n "$TOKEN" ] || { echo "❌ Login failed"; exit 1; }
echo "✅ Login successful"

# 4. Meeting anlegen
MEETING_ID=$(curl -X POST -H "Authorization: Bearer $TOKEN" \
  -d '{"title":"Smoke Test Meeting","start_time":"2026-04-04T10:00:00Z"}' \
  ${STAGING_URL}/api/v1/meetings | jq -r '.id')
[ -n "$MEETING_ID" ] && echo "✅ Meeting created (ID: $MEETING_ID)"

echo "🎉 All smoke tests passed!"
```

---

#### Phase 6: Production Deployment (AKTUELL — SSH-basiert via GitHub Actions)

**Stand 2026-07-29:** `deploy-production.yml` nutzt SSH-Ansatz (kein Docker, kein k3s API auf public IP).

```yaml
# .github/workflows/deploy-production.yml (aktuelle Version)
name: Deploy Production
on:
  workflow_run:
    workflows: ["Docker Build & Push"]
    types: [completed]
    branches: [main]
  workflow_dispatch:

jobs:
  deploy:
    runs-on: ubuntu-latest
    if: ${{ github.event.workflow_run.conclusion == 'success' || github.event_name == 'workflow_dispatch' }}
    steps:
    - uses: actions/checkout@v4

    - name: Copy manifests to Contabo
      uses: appleboy/scp-action@v0.1.7
      with:
        host: 169.58.83.32
        username: root
        key: ${{ secrets.CONTABO_SSH_KEY }}
        source: "infrastructure/kubernetes/production/"
        target: "/root/production-manifests"
        strip_components: 3

    - name: Deploy to Contabo Production
      uses: appleboy/ssh-action@v1
      with:
        host: 169.58.83.32
        username: root
        key: ${{ secrets.CONTABO_SSH_KEY }}
        script: |
          set -e
          echo "=== Deploying Production ==="

          # Pull images directly to k3s containerd (no Docker middleware)
          echo "${{ secrets.DOCKERHUB_TOKEN }}" | k3s ctr images registry login docker.io --username "${{ secrets.DOCKERHUB_USERNAME }}" --password-stdin 2>/dev/null || true

          # Remove cached images to force fresh pull (prevents stale :latest)
          k3s ctr images rm docker.io/batnini/meeting-automation-backend:latest 2>/dev/null || true
          k3s ctr images rm docker.io/batnini/meeting-automation-frontend:latest 2>/dev/null || true

          k3s ctr images pull docker.io/batnini/meeting-automation-backend:latest || {
            echo "Direct pull failed, falling back to docker save"
            docker pull docker.io/batnini/meeting-automation-backend:latest
            docker save docker.io/batnini/meeting-automation-backend:latest | k3s ctr images import -
            docker image rm docker.io/batnini/meeting-automation-backend:latest 2>/dev/null || true
          }
          k3s ctr images pull docker.io/batnini/meeting-automation-frontend:latest || {
            echo "Frontend direct pull failed, trying fallback"
            docker pull docker.io/batnini/meeting-automation-frontend:latest || echo "Frontend image not available"
            docker save docker.io/batnini/meeting-automation-frontend:latest | k3s ctr images import - 2>/dev/null || true
            docker image rm docker.io/batnini/meeting-automation-frontend:latest 2>/dev/null || true
          }

          # Apply manifests
          export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
          cd /root/production-manifests

          kubectl apply -f namespace.yaml
          for secret in backend-secrets postgres-secrets redis-secrets minio-secrets rabbitmq-secrets livekit-secrets n8n-secrets; do
            kubectl get secret "$secret" -n meeting-automation >/dev/null 2>&1 || \
              kubectl apply -f "${secret}.yaml" -n meeting-automation
          done
          kubectl apply -f backend-config.yaml -f livekit-configmap.yaml -f livekit-egress-configmap.yaml -f frontend-nginx-config.yaml
          kubectl apply -f redis-deployment.yaml -f rabbitmq-statefulset.yaml -f minio-statefulset.yaml
          kubectl apply -f cnpg-cluster.yaml
          kubectl apply -f backend-deployment.yaml -f frontend-deployment.yaml -f onlyoffice-deployment.yaml -f n8n-deployment.yaml
          kubectl apply -f celery-worker-deployment.yaml -f celery-worker-pro-deployment.yaml -f celery-beat-deployment.yaml
          kubectl apply -f livekit-server-deployment.yaml -f livekit-egress-deployment.yaml
          kubectl apply -f network-policies.yaml
          kubectl apply -f ingress-prod.yaml

          # Rollout restart
          kubectl rollout restart deployment/backend -n meeting-automation
          kubectl rollout restart deployment/frontend -n meeting-automation
          kubectl rollout restart deployment/celery-worker -n meeting-automation
          kubectl rollout restart deployment/celery-worker-pro -n meeting-automation
          kubectl rollout restart deployment/celery-beat -n meeting-automation

          # Wait for rollout
          kubectl rollout status deployment/backend -n meeting-automation --timeout=180s || true
          kubectl rollout status deployment/frontend -n meeting-automation --timeout=180s || true

          echo "=== Deployment complete ==="
          kubectl get pods -n meeting-automation
```

**Manueller Trigger:**
```bash
gh workflow run deploy-production.yml
```

**Sofort-Deploy nach Secret-Update:**
```bash
gh secret set KUBE_CONFIG_PRODUCTION --body "$(cat ~/.kube/config-prod)"
gh workflow run deploy-production.yml
```

---

#### Phase 7: Post-Deployment Validation (Automated)

```bash
#!/bin/bash
# scripts/validate-production.sh

PROD_URL="https://meeting-automate.tn"

echo "🔍 Post-Deployment Validation"

tests_failed=0

# 1. Backend Health
if curl -sf ${PROD_URL}/health > /dev/null; then
  echo "✅ Backend health"
else
  echo "❌ Backend health FAILED"
  tests_failed=$((tests_failed+1))
fi

# 2. Frontend loads
if curl -sf ${PROD_URL}/ | grep -q "Meeting Automation"; then
  echo "✅ Frontend loads"
else
  echo "❌ Frontend FAILED"
  tests_failed=$((tests_failed+1))
fi

# 3. API Docs accessible
if curl -sf ${PROD_URL}/api/docs | grep -q "swagger"; then
  echo "✅ API docs accessible"
else
  echo "❌ API docs FAILED"
  tests_failed=$((tests_failed+1))
fi

# 4. HTTPS redirection (HTTP → HTTPS)
if curl -sf -I ${PROD_URL//https:/http:} | grep -q "301 Moved Permanently"; then
  echo "✅ HTTP→HTTPS redirect"
else
  echo "⚠️  HTTP→HTTPS redirect check (可能需要手动验证)"
fi

# 5. n8n erreichbar
if curl -sf https://n8n.meeting-automate.tn > /dev/null; then
  echo "✅ n8n accessible"
else
  echo "⚠️  n8n may not be exposed (ok if internal only)"
fi

# 6. Monitoring Dashboard
if curl -sf -H "Authorization: Bearer $(get_tech_admin_token)" \
  ${PROD_URL}/api/v1/admin/metrics | grep -q "container_"; then
  echo "✅ Monitoring metrics endpoint"
else
  echo "❌ Monitoring metrics FAILED"
  tests_failed=$((tests_failed+1))
fi

if [ $tests_failed -eq 0 ]; then
  echo "🎉 All validation checks passed!"
  exit 0
else
  echo "❌ $tests_failed validation checks failed"
  exit 1
fi
```

---

## 🔄 6. Rollback-Plan (aktualisiert 2026-07-29)

### 6.1 Bei fehlgeschlagenem Deployment (Rolling Update)

```bash
# SSH zu Contabo
ssh root@169.58.83.32

# Letztes funktionierendes Deployment zurückrollen
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
kubectl rollout undo deployment/backend -n meeting-automation
kubectl rollout status deployment/backend -n meeting-automation

# Bei Frontend ebenso
kubectl rollout undo deployment/frontend -n meeting-automation
```

### 6.2 Bei DB-Migrationsfehler

**Szenario:** Alembic-Migration schlägt fehl (inkompatible Schema-Änderung).

**Rückrollungs-Schritte:**

1. **Rollback Backend** zur vorherigen Image-Version:
   ```bash
   ssh root@169.58.83.32
   export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
   kubectl set image deployment/backend \
     backend=docker.io/batnini/meeting-automation-backend:previous-tag \
     -n meeting-automation
   ```

2. **DB-Rollback:** Alembic unterstützt kein automatisches Down-Migration für alle Änderungen. Daher:
   - Vor Migration **immer** DB-Backup erstellen (im Deploy-Skripot!)
   - Bei Fehler: DB aus Backup wiederherstellen
   ```bash
   # Backup wiederherstellen
   kubectl exec -i postgres-0 -n meeting-automation -- \
     psql -U meeting_user meeting_db < /backup/db_20260403_020000.sql.gz
   ```

3. **Monitoring:** Überwachen der DB-Health und Application Logs während Rollback.

---

### 6.3 Bei Image-Fehler (Crashing Pods)

```bash
# 1. SSH zu Contabo
ssh root@169.58.83.32
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

# 2. Pods auf Fehler prüfen
kubectl get pods -n meeting-automation
kubectl logs deployment/backend -n meeting-automation --tail=100

# 3. Auf vorheriges Image rollen
kubectl rollout undo deployment/backend -n meeting-automation

# 4. Neue Image-Version mit Hotfix bauen und erneut deployen
# (lokal auf Developer-Machine)
docker build -t batnini/meeting-automation-backend:hotfix-$(date +%s) ./backend
docker push batnini/meeting-automation-backend:hotfix-...
kubectl set image deployment/backend backend=batnini/meeting-automation-backend:hotfix-... -n meeting-automation
```

---

## ✅ 7. Pre-Deployment Checklist (Production Go-Live)

### 7.1 Infrastructure

- [ ] Kubernetes Cluster provisioniert (Terraform apply)
- [ ] Load Balancer aktiv (Traefik Service vom Typ LoadBalancer hat external IP)
- [ ] PersistentVolumeClaims gebunden (Postgres, Redis, MinIO)
- [ ] NetworkPolicies angewendet (`kubectl get networkpolicy -n meeting-automation-prod`)
- [ ] Namespace `meeting-automation-prod` existiert

### 7.2 Secrets & Configuration

- [ ] Alle `*-secrets.yaml` mit Production-Werten verschlüsselt (SOPS)
- [ ] Age-Private-Key gesichert in `~/.config/sops/age/keys.txt` (Backup!)
- [ ] `backend-config.yaml` hat `DEBUG="false"`
- [ ] `CORS_ORIGINS` enthält `https://meeting-automate.tn` (nicht localhost)
- [ ] `ONLYOFFICE_URL` zeigt auf OnlyOffice Service DNS
- [ ] `N8N_WEBHOOK_URL` zeigt auf n8n Service DNS
- [ ] Traefik TLS Secret mit Let's Encrypt Zertifikat (oder eigenem cert)

### 7.3 Images & Deployment

- [ ] Docker Images gepusht zu Docker Hub:
  - `$DOCKERHUB_USERNAME/meeting-automation-backend:latest` (oder tagging mit SHA)
  - `$DOCKERHUB_USERNAME/meeting-automation-frontend:latest`
- [ ] In `backend-deployment.yaml`, `frontend-deployment.yaml`:
  - `imagePullPolicy: Always` (nicht `Never`)
  - Image-Name mit Registry: `$DOCKERHUB_USERNAME/meeting-automation-backend:latest`
- [ ] Resource Limits:
  - Backend: `memory: "2Gi"`, `cpu: "1000m"`
  - Celery Worker: `memory: "4Gi"`, `cpu: "2000m"`
  - PostgreSQL: `memory: "4Gi"`, `cpu: "2000m"`
- [ ] Replicas:
  - Backend: `replicas: 3`
  - Frontend: `replicas: 3`
  - Celery Worker: `replicas: 3`
- [ ] Health Checks:
  - `livenessProbe` path `/health` mit `initialDelaySeconds: 60`
  - `readinessProbe` path `/health` mit `initialDelaySeconds: 30`

### 7.4 Database & Migrations

- [ ] PostgreSQL DB `meeting_db_prod` existiert
- [ ] `alembic upgrade head` erfolgreich auf Production ausgeführt
- [ ] Initial users geseded (falls gewünscht): `scripts/seed_users.py`
- [ ] S3 Bucket `meeting-recordings` existiert

### 7.5 External APIs

- [ ] **Mistral API Key** → Production Key (nicht Test-Key)
- [ ] **Gladia API Key** → Production Key (nicht Test-Key)
- [ ] **SMTP** → SendGrid/SES Production API Key (nicht Gmail)
- [ ] **Stripe** → Live-Mode Secret Key + Webhook-Endpoints konfiguriert
- [ ] **WhatsApp Business** → Production Token konfiguriert
- [ ] **OnlyOffice** → Starkes JWT Secret (nicht Default-Wert)

### 7.6 Monitoring & Alerting

- [ ] Custom Dashboard erreichbar (`/api/v1/admin/metrics`) mit `tech_admin` Token
- [ ] Prometheus installiert (falls verwendet)
- [ ] Grafana Dashboards importiert
- [ ] Alertmanager Rules aktiv
- [ ] Test-Alert versandt an Slack/Telegram/Email

### 7.7 Backup

- [ ] PostgreSQL Backup CronJob deployt
- [ ] Backup-Test durchgeführt: `pg_dump` → MinIO
- [ ] MinIO Versioning aktiviert
- [ ] Restore-Prozess dokumentiert und getestet

### 7.8 Security

- [ ] NetworkPolicies aktiv und getestet (`kubectl describe networkpolicy`)
- [ ] Traefik Rate Limiting aktiv (`kubectl get middleware`)
- [ ] TLS Zertifikat von Let's Encrypt (oder eigenes) gültig
- [ ] Keine Secrets in `docker-compose.yml` oder `.env` für Production
- [ ] Container laufen als non-root user (wenn im Dockerfile konfiguriert)
- [ ] Image-Scanning (Trivy) ohne Critical/High Vulnerabilities

### 7.9 Final Checks

- [ ] DNS `meeting-automate.tn` zeigt auf LoadBalancer IP
- [ ] HTTPS erzwungen (HTTP → 301 Redirect)
- [ ] Alle Health Checks grün: `kubectl get pods -n meeting-automation-prod`
- [ ] DB-Verbindungen funktionieren
- [ ] Redis/PubSub funktioniert (Celery Tasks werden verarbeitet)
- [ ] n8n Workflows aktiviert (manuell in n8n UI importiert)
- [ ] OnlyOffice JWT Token erwünscht

---

## ❓ 8. Offene Fragen & Entscheidungen

### A) Infrastruktur

| Frage | Entscheidung | Offen? |
|-------|--------------|--------|
| Cloud-Anbieter (AWS/GCP/Azure/Hetzner) | **Hetzner** (vom Benutzer erwähnt) | ✅ |
| Terraform Config | Muss geschrieben werden (aktuell TODO) | ❌ |
| Kubernetes Cluster | Wird von Terraform erstellt | ❌ |
| Domain | `meeting-automate.tn` | ✅ |
| Load Balancer | Traefik Service Typ `LoadBalancer` | ✅ |

### B) External APIs

| API | Production Key vorhanden? | Aktion |
|-----|--------------------------|--------|
| Mistral AI | Nein (Test-Key in .env) | 🔴 Key beschaffen |
| Gladia AI | Nein (Test-Key in .env) | 🔴 Key beschaffen |
| OpenAI | In .env vorhanden, aber nicht genutzt? | 🔵 Prüfen ob benötigt |
| Stripe | Test-Mode? | 🔴 Auf Live umstellen + Webhooks |
| SMTP | Gmail (nicht Production) | 🔴 Zu SendGrid/SES wechseln |
| WhatsApp Business API | Token in .env | 🔴 Production Token beantragen |

### C) n8n Workflows

**Status (2026-06-24):** 7 Workflows via n8n API importiert und aktiv ✅

| Workflow | ID | Status |
|----------|-----|--------|
| meeting-created | ergr03uwrFJZJbOT | ✅ Active |
| audio-uploaded | yUabduHmFMTK11jZ | ✅ Active |
| daily-reminders | GpER66AvYwapRNP4 | ✅ Active |
| meeting-status-changed | kf94JbBu2ewnSzS8 | ✅ Active |
| pv-validated | DAd2jClIdg6wJtfy | ✅ Active |
| transcription-completed | BOlWu12gdUfABJWW | ✅ Active |
| user-invited | CqkpcBkdkXlJtZbo | ✅ Active |

**Lösung Optionen:**
1. **PVC** für n8n Data (empfohlen):
   ```yaml
   # n8n Deployment um VolumeMount erweitern
   volumeMounts:
   - name: n8n-data
     mountPath: /home/node/.n8n
   volumes:
   - name: n8n-data
     persistentVolumeClaim:
       claimName: n8n-pvc
   ```
   → Workflows werden in DB gespeichert, DB ist persistent → Workflows bleiben erhalten.

2. **Automatisierter Import** via n8n-API (bereits implementiert):
   - N8N_API_KEY in K8s Secret `n8n-secrets` hinterlegt
   - Import via `POST /api/v1/workflows` mit JSON-Format
   - Aktivierung via `POST /api/v1/workflows/{id}/activate`

**Empfehlung:** Option 1 (PVC) + Option 2 (API-Import) als Fallback.

---

## 📝 9. Deliverables – Was du jetzt tun musst

### Priorität 1 (MUSS vor Production):

1. **Terraform Config schreiben** für deinen Cloud-Anbieter (Hetzner).
   - Oder alternativ: Cluster manuell erstellen und `kubeconfig` bereitstellen.
2. **Production API-Keys beschaffen:**
   - Mistral AI Production Key
   - Gladia AI Production Key
   - SendGrid/SES SMTP Credentials
   - Stripe Live Keys (falls Payment)
   - WhatsApp Business Production Token
3. **Backup-Skript implementieren** (`scripts/backup-db.sh` + CronJob)
4. **k8s/backend-secrets.yaml** um fehlende Keys ergänzen (`ONLYOFFICE_SECRET`, `WHATSAPP_TOKEN`)

### Priorität 2 (innerhalb 1. Woche nach Go-Live):

5. **Prometheus/Grafana installieren** für Monitoring & Alerting
6. **n8n PVC** konfigurieren für Workflow-Persistence
7. **Alertmanager Rules** definieren und Alert-Kanäle (Slack/Telegram) konfigurieren
8. **Backup Retention Policy** definieren und Restore-Tests durchführen

### Priorität 3 (Nice-to-have):

9. **CI/CD Deploy-Pipeline** automatisieren (derzeit nur Build, kein Deploy)
10. **Canary/Blue-Green Deployments** einrichten (ArgoCD oder 手动)
11. **Auto-Scaling (HPA)** für Backend und Celery Worker
12. **Log Aggregation (Loki)** für zentrale Logs

---

## 📞 Kontakt & nächste Schritte

Sobald du die Priorität-1-Aufgaben erledigt hast:

1. Terraform-Config bereitstellen
2. Production API-Keys in `backend-secrets.yaml` eingetragen (SOPS verschlüsselt)
3. Kubernetes Cluster erreichbar (`kubectl get nodes`)

➡️ Dann führe `./scripts/deploy-production.sh` aus.

Bei Problemen: Logs prüfen mit `kubectl logs -f deployment/backend -n meeting-automation-prod`.

---

## 📚 Referenzen

- Kubernetes Manifests: `infrastructure/kubernetes/`
- Protokolle: `docs/PROTOCOL_*.md` (insbesondere PART_27, 28, 29, 30, 31, 33, 35)
- CI/CD: `.github/workflows/`
- Dockerfiles: `backend/Dockerfile`, `frontend/Dockerfile`
- E2E Tests: `tests/e2e/`

---

## 🔒 10. Production TLS/cert-manager Plan

> **Stand:** 2026-08-01
> **Vorbild:** Staging (Phase 183) — cert-manager + Let's Encrypt HTTP-01 + nginx-ingress — funktioniert seit 2026-07-31 stabil

### 10.1 Aktueller Zustand Production

| Komponente | Status | Details |
|------------|--------|---------|
| Domain | ✅ | `meeting-automate.tn` → `169.58.83.32` (Contabo) |
| nginx-ingress | ⚠️ | Installiert, aber NICHT hostNetwork (NodePort-Modus) |
| cert-manager | ❌ **FEHLT** | Nicht installiert |
| ClusterIssuer | ❌ **FEHLT** | Let's Encrypt ACME nicht konfiguriert |
| TLS Secret | ❌ **FEHLT** | Kein Zertifikat vorhanden |
| n8n NodePort 31678 | ❌ | Nicht offen (kein TLS = Passwort im Klartext) |
| HTTP → HTTPS Redirect | ❌ | Kein Redirect (alles plain HTTP) |

### 10.2 Warum identisch zu Staging funktioniert

Staging hatte dasselbe Problem (Phase 183): cert-manager fehlte → kein TLS → Browser-Warnung. Die Lösung war:

1. cert-manager per Helm installieren
2. ClusterIssuer `letsencrypt-prod` erstellen (ACME HTTP-01)
3. Ingress-Annotation `cert-manager.io/cluster-issuer: letsencrypt-prod` hinzufügen
4. TLS Secret Name im Ingress angeben
5. cert-manager stellt automatisch Zertifikat aus

**Dauer:** ~10 Minuten. **Ergebnis:** Gültiges Let's Encrypt Zertifikat (90 Tage Auto-Renew).

### 10.3 Schritt-für-Schritt Plan (Production)

**Voraussetzung:** SSH zu Contabo (`ssh root@169.58.83.32`), `KUBECONFIG=/etc/rancher/k3s/k3s.yaml`

#### Schritt 1: cert-manager installieren

```bash
# CRDs installieren
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.15.0/cert-manager.crds.yaml

# cert-manager per Helm
helm repo add jetstack https://charts.jetstack.io
helm repo update
helm install cert-manager jetstack/cert-manager \
  --namespace cert-manager \
  --create-namespace \
  --version v1.15.0

# Verifizieren (3/3 Pods Running)
kubectl get pods -n cert-manager
```

#### Schritt 2: ClusterIssuer erstellen

```yaml
# cert-manager-issuer-prod.yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: admin@meeting-automate.tn
    privateKeySecretRef:
      name: letsencrypt-prod-key
    solvers:
    - http01:
        ingress:
          class: nginx
```

```bash
kubectl apply -f cert-manager-issuer-prod.yaml
```

#### Schritt 3: Ingress annotieren + TLS Secret

In `infrastructure/kubernetes/production/ingress-prod.yaml`:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: meeting-prod
  namespace: meeting-automation
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod  # ← NEU
    nginx.ingress.kubernetes.io/proxy-body-size: "50m"
    nginx.ingress.kubernetes.io/proxy-read-timeout: "86400"
spec:
  ingressClassName: nginx
  tls:                                    # ← NEU
  - hosts:
    - meeting-automate.tn
    secretName: prod-tls                  # ← NEU (cert-manager erstellt dieses Secret automatisch)
  rules:
  - host: meeting-automate.tn
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: frontend
            port:
              number: 80
      - path: /api
        pathType: Prefix
        backend:
          service:
            name: backend
            port:
              number: 8000
      # ... (weitere Pfade wie /rtc, /doc, /n8n)
```

```bash
kubectl apply -f ingress-prod.yaml
```

#### Schritt 4: Zertifikat ausstellen lassen

```bash
# cert-manager erkennt die Annotation und startet ACME Challenge
# Warten (1-3 Minuten)
kubectl get certificate -n meeting-automation -w

# Verifizieren
kubectl describe certificate prod-tls -n meeting-automation
# Expected: "Certificate is up to date" + "Ready: True"
```

#### Schritt 5: HTTP → HTTPS Redirect

In der Ingress-Annotation hinzufügen:

```yaml
nginx.ingress.kubernetes.io/ssl-redirect: "true"
nginx.ingress.kubernetes.io/force-ssl-redirect: "true"
```

#### Schritt 6: n8n hinter Ingress + TLS (optional)

Falls n8n auch über Domain erreichbar sein soll (statt NodePort):

```yaml
# In ingress-prod.yaml additional paths:
      - path: /n8n
        pathType: Prefix
        backend:
          service:
            name: n8n
            port:
              number: 5678
```

**ACHTUNG:** n8n braucht `N8N_PATH=/n8n/` wenn es unter Subpath läuft (siehe Staging-Analyse). Ohne NodePort reicht der Ingress.

### 10.4 Verifikation nach TLS-Setup

| # | Check | Erwartung | Befehl |
|---|-------|-----------|--------|
| 1 | HTTP Redirect | `301/308 → HTTPS` | `curl -I http://meeting-automate.tn` |
| 2 | HTTPS Status | `200` | `curl -k https://meeting-automate.tn` |
| 3 | TLS Zertifikat | Let's Encrypt (NICHT self-signed) | `openssl s_client -connect meeting-automate.tn:443 < /dev/null 2>/dev/null | openssl x509 -noout -issuer` |
| 4 | Certificate Resource | `READY=True` | `kubectl get certificate -n meeting-automation` |
| 5 | n8n (falls Ingress) | Login-Seite unter HTTPS | `curl -k https://meeting-automate.tn/n8n/` |
| 6 | HSTS Header | `max-age=31536000` | `curl -kI https://meeting-automate.tn | grep -i strict` |

### 10.5 Bekannte Risiken (aus Staging gelernt)

| # | Risiko | Lösung (bewiesen auf Staging) |
|---|--------|-------------------------------|
| R1 | `default-deny-all` blockiert ACME Solver-Pod | NetworkPolicy `acme-solver-allow-ingress` erstellen (Label `acme.cert-manager.io/http01-solver=true`, Port 8089/30172) |
| R2 | Ingress `/n8n` zeigt weiße Seite | n8n NodePort 31678 ODER `N8N_PATH=/n8n/` setzen |
| R3 | cert-manager erstellt Solver-Pod in falschem Namespace | Certificate-Objekt MUSS im selben Namespace wie Ingress sein |
| R4 | Auto-Renewal scheitert (DNS-Problem) | HTTP-01 funktioniert OHNE DNS-Änderung — nur Port 80 muss offen sein |

### 10.6 n8n Zugang nach TLS

| Option | URL | TLS | Auth |
|--------|-----|-----|------|
| **A: Ingress Subpath** | `https://meeting-automate.tn/n8n/` | ✅ Let's Encrypt | n8n Owner-Account |
| **B: NodePort** | `http://169.58.83.32:31678` | ❌ Klartext | n8n Owner-Account |
| **C: Separater Ingress** | `https://n8n.meeting-automate.tn` | ✅ Eigene DNS + Cert | n8n Owner-Account |

**Empfehlung:** Option A (Ingress Subpath) — sicherster Weg, kein zusätzlicher Port, TLS included.

---

**Erstellt:** 2026-04-03
**Autor:** Claude Code
**Status:** Production Deployment Ready (nach Completion der Priorität-1-Aufgaben)
