# Staging Cluster Setup Plan

## 🎯 Ziel

Einrichtung eines Kubernetes Staging-Clusters, das die **Produktionsumgebung exakt widerspiegelt**, um sichere E2E-Tests vor dem Production-Deploy zu ermöglichen. Das Setup muss sowohl **lokal** (für Entwicklung) als auch **extern/cloud** (für CI/CD) funktionieren.

---

## 📋 Anforderungen

### 1. Environments

| Environment | Zweck | Daten-Isolation | Empfohlen für |
|-------------|-------|-----------------|---------------|
| **DEV (docker-compose)** | Lokale Entwicklung | Ephemeral (fresh DB) | Devs lokal |
| **STAGING** | Pre-Production Validierung | Dedicated DB + isolate services | CI/CD Pipeline |
| **PRODUCTION** | Live Kundendaten | Production DB | Nur manuelle Smoke Tests |

### 2. Staging Cluster Spezifikationen

- **Namespace**: `meeting-automation-staging`
- **Domain**: `staging.meeting-automate.tn` (Traefik Ingress)
- **Services**:
  - PostgreSQL (mit persistent storage)
  - Redis
  - RabbitMQ
  - MinIO (S3-compatible)
  - n8n (Workflow Automation)
  - OnlyOffice (Document Server)
  - Backend (2 replicas minimum)
  - Celery Worker & Beat
- **Health Check**: `/health` endpoint (unauthenticated)
- **Resource Limits** (siehe PROTOCOL_PART_35):
  - Backend: 0.5 CPU, 1Gi RAM
  - Celery-Worker: 0.5 CPU, 512Mi RAM
  - Andere: 0.5 CPU, 512Mi RAM

### 3. Secrets Management

Staging Secrets in GitHub Actions (Repository Settings → Secrets):

| Secret Name | Beschreibung | Woher beziehen |
|-------------|--------------|----------------|
| `DOCKERHUB_TOKEN` | Docker Hub Access Token mit `write:packages` | Docker Hub → Settings → Security |
| `KUBE_CONFIG_STAGING` | Kubeconfig für Staging-Cluster (vollständiger Inhalt) | Siehe Abschnitt 2 unten |
| `STAGING_E2E_USER_EMAIL` | E-Mail des E2E-Test-Users | Vorgeschlagen: `e2e-tester@staging.meeting.tn` |
| `STAGING_E2E_USER_PASSWORD` | Passwort des E2E-Test-Users | Vorgeschlagen: `Password123!` (kann geändert werden) |
| `MISTRAL_API_KEY_STAGING` | Mistral AI API Key für Staging | Aus `.env` oder neuer Test-Key |
| `GLADIA_API_KEY_STAGING` | Gladia API Key für Staging | Aus `.env` oder neuer Test-Key |

---

## 🛠️ Option 1: Lokales Staging Cluster (Docker Desktop / Kind)

### 1.1 Voraussetzungen

- Docker Desktop (mit Kubernetes aktiviert) **ODER** Kind (Kubernetes in Docker)
- `kubectl` installiert und konfiguriert
- `kustomize` oder `kubectl kustomize` (optional, für manifold management)

### 1.2 Cluster erstellen

#### Mit Docker Desktop:
1. Docker Desktop öffnen → Settings → Kubernetes → ✅ "Enable Kubernetes"
2. Apply & Restart (ca. 5–10 Min.)
3. Prüfen: `kubectl cluster-info`

#### Mit Kind (empfohlen für CI-Lokalität):
```bash
# Installiere Kind: https://kind.sigs.k8s.io/
kind create cluster --name meeting-staging
# Setze Kontext:
kubectl config use-context kind-meeting-staging
```

### 1.3 Staging Namespace & Infrastruktur deployen

Das Skript `./setup-kubernetes.sh` (aus PROTOCOL_PART_29) automatisiert dies:

```bash
# 1. SOPS/age Keys sicherstellen (wenn verschlüsselte Secrets)
./bin/sops --version  # prüfen
# Falls nicht vorhanden: age Key generieren (oder aus backup)

# 2. Setup-Skript ausführen (erstellt Namespace, Secrets, DB, etc.)
./backend/scripts/setup-kubernetes.sh

# 3. Prüfen, ob alles läuft:
kubectl get pods -n meeting-automation-staging
# Alle Pods sollten "Running" oder "Completed" sein
```

**Hinweis**: Das Skript erwartet einen Context namens `staging-cluster`. Wenn du `kind` verwendest:

```bash
# Context in staging-cluster umbenennen (optional):
kubectl config rename-context kind-meeting-staging staging-cluster
```

### 1.4 Kubeconfig für GitHub Secrets exportieren

```bash
# Hole den aktuellen Context (sollte staging-cluster sein)
kubectl config current-context

# Exportiere die vollständige kubeconfig für diesen Context
kubectl config view --context=staging-cluster --raw > kubeconfig-staging.txt

# Kürzen auf notwendige Teile (optional, aber empfohlen):
# Die Datei sollte enthalten: clusters, contexts, users (mit token/cert data)

# Für GitHub Actions: Inhalt der Datei kopieren und als Secret
# GitHub → Settings → Secrets and variables → Actions → New repository secret
# Name: KUBE_CONFIG_STAGING
# Value: [Inhalt von kubeconfig-staging.txt]
```

### 1.5 Test-User in Staging-DB anlegen

Das `setup-kubernetes.sh` Skript führt bereits `seed_users.py` aus. Wenn nicht:

```bash
# Manuell: Backend-Pod exec und seed ausführen
POD=$(kubectl get pods -n meeting-automation-staging -l app=backend -o jsonpath="{.items[0].metadata.name}")
kubectl exec -n meeting-automation-staging $POD -- python backend/scripts/seed_users.py

# Prüfen, ob User existiert:
kubectl exec -n meeting-automation-staging $POD -- psql -U meeting_user -d meeting_db_staging -c "SELECT email FROM users WHERE email='e2e-tester@staging.example.com';"
```

---

## ☁️ Option 2: Externes/Cloud Staging Cluster (AWS EKS, GKE, Azure AKS, DigitalOcean)

### 2.1 Cluster Provisionierung

Wähle deinen Cloud-Provider und erstelle einen Kubernetes-Cluster mit:

- **Region**: Wähle eine Region nahe deinem Standort
- **Version**: Kubernetes 1.28+ (kompatibel mit den Manifests)
- **Node Pools**:
  - 2x `standard-medium` (2 CPUs, 4GB RAM) für App-Pods
  - Optional: 1x `standard-small` für DB (oder managed DB service)
- **Networking**:
  - VPC mit öffentlicher IP für Ingress (Traefik)
  - DNS: `staging.meeting-automate.tn` auf LoadBalancer-IP zeigen
- **Storage**: PersistentVolumeClass für Postgres-Daten (z.B. `gp2` auf AWS)

#### Beispiel: Terraform (empfohlen)

```hcl
# infrastructure/terraform/staging/main.tf
resource "helm_release" "traefik" {
  name       = "traefik"
  repository = "https://helm.traefik.io/traefik"
  chart      = "traefik"
  namespace  = "kube-system"
}

resource "kubernetes_namespace" "staging" {
  metadata {
    name = "meeting-automation-staging"
  }
}

# Weitere Ressourcen: Postgres (StatefulSet), Redis, etc.
# ODER verwende managed services (RDS, ElastiCache, etc.)
```

### 2.2 Ingress & DNS

**Traefik als Ingress Controller** (bereits in Manifests):

```bash
# Traefik installieren (falls nicht vorhanden)
helm repo add traefik https://helm.traefik.io/traefik
helm install traefik traefik/traefik --namespace kube-system
```

**DNS konfigurieren**:

```bash
# 1. Traefik LoadBalancer IP auslesen
kubectl get svc -n kube-system traefik
# OUTPUT: EXTERNAL-IP: 34.123.45.67

# 2. DNS A-Record setzen:
# staging.meeting-automate.tn → 34.123.45.67
# (Bei deinem DNS-Provider: Cloudflare, GoDaddy, Route53, etc.)
```

**Traefik IngressRoute validieren**:

```yaml
# infrastructure/kubernetes/staging/traefik-ingressroute.yaml
apiVersion: traefik.containo.us/v1alpha1
kind: IngressRoute
metadata:
  name: backend-ingress
  namespace: meeting-automation-staging
spec:
  entryPoints:
    - websecure
  routes:
    - match: Host(`staging.meeting-automate.tn`)
      kind: Rule
      services:
        - name: backend
          port: 8000
```

### 2.3 Kubeconfig erhalten und in GitHub Secrets eintragen

```bash
# 1. Kubeconfig von Local zu Cluster herunterladen (je nach Provider)

# AWS EKS:
aws eks update-kubeconfig --region eu-west-1 --name meeting-staging-cluster --kubeconfig ./kubeconfig-staging

# Google GKE:
gcloud container clusters get-credentials meeting-staging --region europe-west1 --kubeconfig ./kubeconfig-staging

# Azure AKS:
az aks get-credentials --resource-group meet-automation-rg --name meeting-staging --file ./kubeconfig-staging

# DigitalOcean:
doctl kubernetes cluster kubeconfig save meeting-staging --kubeconfig-file ./kubeconfig-staging
```

```bash
# 2. Prüfen:
kubectl --kubeconfig=./kubeconfig-staging get nodes
# Sollte die Nodes des Clusters anzeigen.

# 3. Inhalt kopieren für GitHub Secret:
cat kubeconfig-staging
# COPY ALL
```

**In GitHub eintragen**:
- Repository → Settings → Secrets and variables → Actions → New repository secret
- Name: `KUBE_CONFIG_STAGING`
- Value: [ gesamter Inhalt der kubeconfig-staging-Datei ]

### 2.4 Staging Secrets setzen

Die CI-Pipeline erstellt Secrets automatisch aus GitHub Secrets (siehe `.github/workflows/e2e-tests.yml`, Step "Create/Update Staging Secrets from GitHub Secrets").

Stelle sicher, dass folgende Secrets in GitHub existieren:

```bash
# API Keys (aus deiner lokalen .env)
MISTRAL_API_KEY_STAGING=f0w0biJU2uurFRXXvXo3zQmOW1zap1VU
GLADIA_API_KEY_STAGING=0caddff8-895b-4e18-8acd-40aa8756fa6a

# E2E Test User
STAGING_E2E_USER_EMAIL=e2e-tester@staging.meeting.tn
STAGING_E2E_USER_PASSWORD=Password123!

# Docker Hub Token (schon gesetzt)
DOCKERHUB_TOKEN=xxxx
```

---

## 🧪 Pipeline nach Deploy der Infrastruktur triggern

Sobald:
1. Kubeconfig in GitHub Secrets (`KUBE_CONFIG_STAGING`) gesetzt ist
2. Alle anderen Secrets vorhanden sind
3. DNS auf `staging.meeting-automate.tn` zeigt

Pushe einen Commit, um die GitHub Actions Pipeline auszulösen:

```bash
git add .
git commit -m "ci: trigger staging deployment after infra setup"
git push origin main
```

Die Pipeline führt dann automatisch:
1. Build backend & push to Docker Hub
2. Deploy zu Staging
3. Run full E2E suite
4. Pass-Gate ≥85% (temporär) oder ≥95% (final)

---

## 🐛 Troubleshooting

### Problem: "kubectl get pods" zeigt keinePods

**Check**:
```bash
kubectl config get-contexts  # Ist staging-cluster aktiv?
kubectl get nodes           # Sind Nodes vorhanden?
```

**Lösung**: Falscher Context → `kubectl config use-context staging-cluster`

---

### Problem: Ingress/Route nicht erreichbar

**Check**:
```bash
kubectl get ingressroute -n meeting-automation-staging
kubectl describe ingressroute backend-ingress -n meeting-automation-staging

# Traefik Service prüfen:
kubectl get svc -n kube-system traefik
# EXTERNAL-IP muss Lottery sein.
```

**Lösung**:
1. LoadBalancer-IP zu DNS `staging.meeting-automate.tn` mappen
2. Firewall/Port 80/443 offen

---

### Problem: E2E tests fail with connection timeout

**Check**:
```bash
# Health Check lokal:
curl -v https://staging.meeting-automate.tn/health

# Backend Logs:
kubectl logs -f deployment/backend -n meeting-automation-staging
```

**Lösung**:
- Backend-Pods prüfen: `kubectl get pods -n meeting-automation-staging`
- Eventuell Ressourcenlimits anpassen (PROTOCOL_PART_35)
- DB/Redis/RabbitMQ Connectivity prüfen

---

### Problem: E2E-Test-User nicht gefunden

Pipeline erstellt den User via `kubectl create secret` und `curl` registration API. Wenn das fehlschlägt:

```bash
# Manuell anlegen:
# 1. Secret erstellen:
kubectl create secret generic e2e-test-user \
  --namespace meeting-automation-staging \
  --from-literal=E2E_TEST_USER_EMAIL="e2e-tester@staging.meeting.tn" \
  --from-literal=E2E_TEST_USER_PASSWORD="Password123!" \
  --dry-run=client -o yaml | kubectl apply -f -

# 2. In Staging-DB checken (über backend pod):
POD=$(kubectl get pods -n meeting-automation-staging -l app=backend -o jsonpath="{.items[0].metadata.name}")
kubectl exec -n meeting-automation-staging $POD -- python -c "
from app.core.database import AsyncSessionLocal
from app.models.user import User
from sqlalchemy import select
import asyncio
async def check():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email=='e2e-tester@staging.meeting.tn'))
        user = result.scalar_one_or_none()
        print('User exists:', user is not None)
        if user:
            print('User ID:', user.id)
asyncio.run(check())
"
```

---

## 📈 Pass-Gate Management

### Aktueller Status (Sprint 2-3 Stabilisierung):
- **Staging Pass-Gate**: ≥85% (temporär)
- **Ziel**: ≥95% nach Issues #3 #4 #5/6

### Pass-Gate anpassen:

```bash
# In .github/workflows/e2e-tests.yml, Zeile 263:
if [ $PASS_RATE -lt 85 ]; then   # temporary threshold
#                                 ^^^ anpassen zu 95 nach Stabilisierung
```

Nach Stabilisierung.commit und pushen.

---

## ✅ Checkliste "Staging Ready for E2E"

- [ ] Kubernetes Cluster (lokal oder cloud) ist erreichbar
- [ ] Context `staging-cluster` ist in kubectl konfiguriert
- [ ] Namespace `meeting-automation-staging` existiert
- [ ] Alle Infrastruktur-Pods sind Running (Postgres, Redis, RabbitMQ, MinIO, n8n, OnlyOffice)
- [ ] Backend deployed mit Image-Tag von GitHub Actions
- [ ] Traefik IngressRoute für `staging.meeting-automate.tn` konfiguriert
- [ ] DNS zeigt auf Traefik LoadBalancer IP
- [ ] Health Check: `curl https://staging.meeting-automate.tn/health` returns `{"status":"healthy"}`
- [ ] GitHub Secret `KUBE_CONFIG_STAGING` gesetzt
- [ ] GitHub Secrets `STAGING_E2E_USER_EMAIL`, `STAGING_E2E_USER_PASSWORD` gesetzt
- [ ] GitHub Secrets `MISTRAL_API_KEY_STAGING`, `GLADIA_API_KEY_STAGING` gesetzt
- [ ] GitHub Secret `DOCKERHUB_TOKEN` gesetzt
- [ ] Pipeline Job 2 (deploy-staging-and-test) wird ausgelöst
- [ ] Staging E2E Pass-Rate ≥85% (temporär) oder ≥95%

---

## 🔄 Regelmäßige Wartung

- **Secrets rotieren**: API-Keys (Mistral, Gladia) regelmäßig ändern und in GitHub Secrets updaten
- **Cluster-Updates**: Kubernetes Version aktualisieren (alle 3–6 Monate)
- **Datenbank-Backups**: Postgres Volume regelmäßig sichern (z.B. mit Velero oder `pg_dump`)
- **Resource Monitoring**: Pod-Limits bei Bedarf anpassen (PROTOCOL_PART_35)

---

## 📚 Referenzen

- `PROTOCOL_PART_29_KUBERNETES_SETUP_SCRIPT.md` – Das automatisierte Setup-Skript
- `PROTOCOL_PART_35_KUBERNETES_STABILITY_AND_RESOURCES.md` – Ressourcen-Limits & Probes
- `E2E_TESTING_STRATEGY.md` – Gesamte Test-Pipeline
- `DEPLOYMENT.md` – Production Deployment Guide
- `docs/PRODUCTION_DEPLOYMENT_PLAN.md` – Detaillierter Produktions-Plan

---

## 🚀 Nächste Schritte

1. Lokales Staging mit `kind` oder Docker Desktop aufsetzen (siehe Option 1)
2. `kubeconfig-staging` exportieren und in GitHub Secrets eintragen
3. GitHub Secrets `STAGING_E2E_USER_*`, `MISTRAL_API_KEY_STAGING`, `GLADIA_API_KEY_STAGING` setzen
4. Pipeline triggern durch Push zu main
5. Job 2 beobachten und Ergebnisse prüfen
6. Bei Erfolg: Pass-Gate ≥95% erhöhen (sobald stabil)

---

## 📋 Production Deployment Roadmap (Übersicht)

Nach erfolgreichem Staging folgt Production. Siehe `docs/PRODUCTION_DEPLOYMENT_PLAN.md` für vollständige Details.

### Phase 1: Infrastructure Provisioning (Cloud)

- **Cloud Provider wählen**: AWS EKS, GKE, Azure AKS, DigitalOcean, oder Hetzner
- **Terraform**: `infrastructure/terraform/production` (aktuell TODO – muss erstellt werden)
- **Cluster größen**: 
  - 3x Worker Nodes (mind. 2 CPUs, 4GB RAM each)
  - Managed PostgreSQL (oder StatefulSet mit persistent volumes)
- **LoadBalancer**: Traefik Service Typ `LoadBalancer` → External IP
- **DNS**: `meeting-automate.tn` → LoadBalancer IP

### Phase 2: Prepare Production Secrets

- Production API Keys beschaffen:
  - Mistral AI (Production)
  - Gladia AI (Production)
  - SendGrid/SES (SMTP)
  - Stripe (Live Mode)
  - WhatsApp Business API
- `backend-secrets.yaml` mit Production-Werten aktualisieren (SOPS verschlüsseln)
- `backend-config.yaml` anpassen:
  - `DEBUG="false"`
  - `CORS_ORIGINS='["https://meeting-automate.tn"]'`
  - Production URLs (n8n, onlyoffice, s3)

### Phase 3: TLS/HTTPS (Let's Encrypt)

- cert-manager installieren
- ClusterIssuer für Let's Encrypt Production konfigurieren
- `traefik-tls-secret.yaml` mit ACME Challenge
- IngressRoute für `meeting-automate.tn` mit TLS

### Phase 4: Production Deployment

```bash
# Namespace production
kubectl apply -f infrastructure/kubernetes/ --namespace=meeting-automation-prod

# Warten auf Infrastruktur
kubectl wait --for=condition=ready pod -l app=postgres -n meeting-automation-prod --timeout=180s
kubectl wait --for=condition=ready pod -l app=redis -n meeting-automation-prod --timeout=120s

# Deploy App
kubectl apply -f infrastructure/kubernetes/backend-deployment.yaml -n meeting-automation-prod
kubectl apply -f infrastructure/kubernetes/celery-*.yaml -n meeting-automation-prod
kubectl apply -f infrastructure/kubernetes/traefik-*.yaml -n meeting-automation-prod

# DB Migration
kubectl exec -i deployment/backend -n meeting-automation-prod -- alembic upgrade head
```

### Phase 5: Post-Deployment Validation

- Smoke Tests (`scripts/validate-production.sh`)
- Monitoring: Custom Dashboard, Prometheus Metrics
- Alerting: Alertmanager Rules aktivieren
- Backup: PostgreSQL CronJob + MinIO Versioning

### Phase 6: Rollback-Plan

- `kubectl rollout undo deployment/backend -n meeting-automation-prod`
- DB Restore aus S3 Backup (`pg_dump` → restore)
- Image Rollback: `kubectl set image deployment/backend backend=previous-tag`

---

## ✅ Pre-Production Checklist

**Infrastructure:**
- [ ] Kubernetes Cluster (cloud) provisioniert
- [ ] LoadBalancer External IP verfügbar
- [ ] DNS `meeting-automate.tn` → LB IP
- [ ] PersistentVolumes für Postgres, MinIO

**Secrets:**
- [ ] Alle `*-secrets.yaml` mit Production-Werten (SOPS verschlüsselt)
- [ ] Age Private Key gesichert
- [ ] GitHub Actions Secrets für Production (falls CI/CD verwendet)

**Security:**
- [ ] NetworkPolicies `default-deny` aktiv
- [ ] Traefik Rate Limiting (50 req/s, 5 req/s für auth)
- [ ] TLS Zertifikat (Let's Encrypt) gültig
- [ ] Keine Secrets im Klartext

**Monitoring & Backup:**
- [ ] Custom Dashboard `/api/v1/admin/metrics` erreichbar
- [ ] Prometheus/Grafana installiert (optional)
- [ ] PostgreSQL Backup CronJob deployt
- [ ] MinIO Versioning aktiviert
- [ ] Backup Restore getestet

**External APIs:**
- [ ] Mistral AI Production Key
- [ ] Gladia AI Production Key
- [ ] SMTP (SendGrid/SES) Production
- [ ] Stripe Live Keys + Webhooks
- [ ] WhatsApp Business Production Token

---

## 📊 Comparison: Local Dev → Staging → Production

| Environment | Orchestration | Namespace | Domain | TLS | CI/CD | Secrets |
|-------------|---------------|-----------|--------|-----|-------|---------|
| **DEV** | docker-compose | N/A | localhost | none | lokal | .env (plain) |
| **STAGING (local)** | Kind K8s | meeting-automation-staging | staging.meeting-automate.tn (HTTP only) | Self-signed (optional) | GitHub Actions (kubeconfig local) | GitHub Secrets |
| **STAGING (cloud)** | K8s (cloud) | meeting-automation-staging | staging.meeting-automate.tn | Let's Encrypt Staging | GitHub Actions (kubeconfig cloud) | GitHub Secrets |
| **PRODUCTION** | K8s (cloud) | meeting-automation-prod | meeting-automate.tn | Let's Encrypt Production | Manual Approval | SOPS encrypted + Vault (optional) |

---

**Bei Fragen oder Blockaden**: Siehe Troubleshooting oder Issues im Repository eröffnen.

