#!/usr/bin/env bash

################################################################################
# Staging Cluster Setup Script
#
# Automatisiert die Einrichtung eines Kubernetes Staging-Clusters für
# Meeting Automation (lokal mit Kind oder cloud-basiert).
#
# Usage:
#   ./scripts/setup-staging-cluster.sh [OPTIONS]
#
# Options:
#   --env, -e ENV          Environment: local, aws, gcp, azure, do (default: local)
#   --kubeconfig, -k PATH  Pfad zur kubeconfig (default: ~/.kube/config)
#   --context, -c NAME     Kubernetes context name (default: staging-cluster)
#   --export-kubeconfig    Kubeconfig für GitHub Secrets exportieren (kubeconfig-staging.txt)
#   --skip-infra           Infrastructure Deployment überspringen
#   --skip-seeds           User Seeding überspringen
#   --help, -h             Diese Hilfe anzeigen
#
# Beispiele:
#   # Lokales Staging mit Kind:
#   kind create cluster --name meeting-staging
#   kubectl config rename-context kind-meeting-staging staging-cluster
#   ./scripts/setup-staging-cluster.sh --env local
#
#   # Nach Setup: Kubeconfig exportieren für GitHub Secrets:
#   ./scripts/setup-staging-cluster.sh --export-kubeconfig
#
# Voraussetzungen:
#   - kubectl installiert
#   - Kubernetes Cluster bereits provisioniert (oder Kind)
#   - Docker (für lokales Image-Building)
#   - kind (für lokales Cluster)
#
# Siehe: docs/STAGING_CLUSTER_SETUP_PLAN.md für vollständige Dokumentation.
################################################################################

set -euo pipefail

# Farbcodes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Defaults
ENVIRONMENT="local"
KUBECONFIG_PATH="${HOME}/.kube/config"
CONTEXT_NAME="staging-cluster"
EXPORT_KUBECONFIG=false
SKIP_INFRASTRUCTURE=false
SKIP_SEEDS=false
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
INFRA_DIR="${PROJECT_ROOT}/infrastructure/kubernetes/staging"

# Logging Functions
log_info()    { echo -e "${BLUE}[INFO]${NC} $*"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $*"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $*"; }

# Help
show_help() {
    grep '^#' "$0" | sed 's/^# //;s/^#//' | head -30
    exit 0
}

# Parse Arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --env|-e)        ENVIRONMENT="$2"; shift 2 ;;
        --kubeconfig|-k) KUBECONFIG_PATH="$2"; shift 2 ;;
        --context|-c)    CONTEXT_NAME="$2"; shift 2 ;;
        --export-kubeconfig) EXPORT_KUBECONFIG=true; shift ;;
        --skip-infra)     SKIP_INFRASTRUCTURE=true; shift ;;
        --skip-seeds)     SKIP_SEEDS=true; shift ;;
        --help|-h)       show_help ;;
        *) log_error "Unbekannte Option: $1"; show_help ;;
    esac
done

# Header
cat << "EOF"
==================================================
   Staging Cluster Setup
==================================================
EOF
log_info "Environment: ${ENVIRONMENT}"
log_info "Kubeconfig:  ${KUBECONFIG_PATH}"
log_info "Context:     ${CONTEXT_NAME}"
log_info "Infra:       $([ "$SKIP_INFRASTRUCTURE" = true ] && echo 'SKIP' || echo 'DEPLOY')"
log_info "Seeds:       $([ "$SKIP_SEEDS" = true ] && echo 'SKIP' || echo 'DEPLOY')"
echo "=================================================="
echo ""

# 1. Prüfe kubectl
log_info "Prüfe kubectl Konfiguration..."
if ! command -v kubectl &> /dev/null; then
    log_error "kubectl ist nicht installiert."
    exit 1
fi

export KUBECONFIG="${KUBECONFIG_PATH}"

# 2. Prüfe Context
if kubectl config get-contexts 2>/dev/null | awk 'NR==1{next} {print $2}' | grep -qx "${CONTEXT_NAME}"; then
    log_success "Context '${CONTEXT_NAME}' gefunden."
    kubectl config use-context "${CONTEXT_NAME}" > /dev/null
else
    log_error "Context '${CONTEXT_NAME}' nicht gefunden."
    log_info "Verfügbare Contexts:"
    kubectl config get-contexts 2>/dev/null || true
    exit 1
fi

# 3. Prüfe Traefik Installation
log_info "Prüfe, ob Traefik Ingress Controller installiert ist..."
if ! kubectl get pods -n kube-system -l app.kubernetes.io/name=traefik &> /dev/null && \
   ! kubectl get pods -n "${NAMESPACE:-kube-system}" -l app.kubernetes.io/name=traefik &> /dev/null; then
    log_error "Traefik ist nicht installiert!"
    log_info "Bitte installiere Traefik zuerst:"
    log_info "  ./scripts/setup-traefik.sh"
    log_info "oder manuell: https://helm.traefik.io/traefik"
    exit 1
fi
log_success "Traefik ist installiert."

# 4. Namespace
log_info "Prüfe/erstelle Namespace 'meeting-automation-staging'..."
if kubectl get namespace meeting-automation-staging &> /dev/null; then
    log_success "Namespace existiert bereits."
else
    if [ -f "${INFRA_DIR}/namespace.yaml" ]; then
        kubectl apply -f "${INFRA_DIR}/namespace.yaml"
        log_success "Namespace erstellt."
    else
        log_error "namespace.yaml nicht gefunden in ${INFRA_DIR}"
        exit 1
    fi
fi

# 4. Lokales Docker Image bauen (nur für local environment)
if [ "${ENVIRONMENT}" = "local" ]; then
    log_info "Bereite lokales Docker Image vor..."
    if docker images | grep -q meeting-automation-backend; then
        log_info "Verwende vorhandenes Docker Image."
    else
        log_info "Baue Docker Image lokal..."
        (cd "${PROJECT_ROOT}/backend" && docker build -t meeting-automation-backend:latest .)
    fi

    # In Kind Cluster importieren
    if command -v kind &> /dev/null; then
        KIND_CLUSTER_NAME="${CONTEXT_NAME#kind-}"
        if [[ "${CONTEXT_NAME}" == kind-* ]] && kind get clusters | grep -q "^${KIND_CLUSTER_NAME}$"; then
            log_info "Lade Image in Kind Cluster '${KIND_CLUSTER_NAME}'..."
            kind load docker-image meeting-automation-backend:latest --name "${KIND_CLUSTER_NAME}"
        fi
    fi
fi

# 5. Infrastructure Deploy (wenn nicht übersprungen)
if [ "${SKIP_INFRASTRUCTURE}" = false ]; then
    log_info "Deploye Infrastruktur..."
    echo ""

    # Manifeste in korrekter Reihenfolge (abhängigkeiten beachten)
    MANIFESTS=(
        # Database & Cache
        "postgres-secrets.yaml"
        "postgres-statefulset.yaml"
        "redis-secrets.yaml"
        "redis-deployment.yaml"
        "rabbitmq-secrets.yaml"
        "rabbitmq-statefulset.yaml"
        # Object Storage
        "minio-secrets.yaml"
        "minio-statefulset.yaml"
        # Automation & Office
        "n8n-secrets.yaml"
        "n8n-deployment.yaml"
        "onlyoffice-deployment.yaml"
        # Backend (benötigt backend-secrets & backend-config)
        "backend-secrets.yaml"
        "backend-config.yaml"
        "celery-worker-deployment.yaml"
        "celery-worker-pro-deployment.yaml"
        "celery-beat-deployment.yaml"
        "backend-deployment.yaml"
        # Ingress
        "traefik-middlewares.yaml"
        "traefik-ingressroute.yaml"
    )

    DEPLOY_COUNT=0
    for manifest in "${MANIFESTS[@]}"; do
        path="${INFRA_DIR}/${manifest}"
        if [ ! -f "$path" ]; then
            log_warn "Manifest nicht gefunden, überspringe: ${manifest}"
            continue
        fi

        log_info "Apply: ${manifest}"
        if kubectl apply -f "$path" -n meeting-automation-staging 2>/dev/null; then
            log_success "  ✓ applied"
            DEPLOY_COUNT=$((DEPLOY_COUNT+1))
        else
            log_error "  ✗ failed to apply"
            exit 1
        fi
    done

    echo ""
    log_success "Infrastruktur deployed (${DEPLOY_COUNT} Manifests)."

    # Warte auf PostgreSQL
    log_info "Warte auf PostgreSQL readiness (timeout: 180s)..."
    if kubectl wait --for=condition=ready pod/postgres-staging-0 -n meeting-automation-staging --timeout=180s 2>/dev/null; then
        log_success "PostgreSQL bereit."
    else
        log_warn "PostgreSQL timeout – prüfe manuell:"
        log_info "  kubectl get pods -n meeting-automation-staging"
    fi
else
    log_warn "Infrastructure Deployment übersprungen."
fi

# 6. Backend Image setzen und Rollout warten
log_info "Stelle sicher, dass Backend Deployment existiert..."

if ! kubectl get deployment backend -n meeting-automation-staging &> /dev/null; then
    log_error "Backend Deployment nicht gefunden. Bitte stelle sicher, dass backend-deployment.yaml angewendet wurde."
    exit 1
fi

# Setze Image-Tag basierend auf Environment
if [ "${ENVIRONMENT}" = "local" ]; then
    IMAGE_TAG="meeting-automation-backend:latest"
else
    # Cloud: Image von Docker Hub (CI pusht es)
    IMAGE_TAG="docker.io/batnini/meeting-automation-backend:latest"
    # In CI wird COMMIT_SHA gesetzt sein – hier nehmen wir latest für Setup
fi

log_info "Setze Backend Image auf: ${IMAGE_TAG}"
if kubectl set image deployment/backend backend="${IMAGE_TAG}" -n meeting-automation-staging --record 2>/dev/null; then
    log_success "Image gesetzt."
else
    log_warn "Konnte Image nicht setzen (evtl. bereits korrekt)."
fi

log_info "Warte auf Backend Rollout (timeout: 300s)..."
if kubectl rollout status deployment/backend -n meeting-automation-staging --timeout=300s; then
    log_success "Backend Rollout abgeschlossen."
else
    log_error "Backend Rollout fehlgeschlagen."
    log_info "Letzte Logs:"
    kubectl logs deployment/backend -n meeting-automation-staging --tail=50 2>/dev/null || true
    exit 1
fi

# 7. Ingress Routes (Traefik) – nochmal anwenden falls übersprungen
log_info "Konfiguriere Traefik Ingress..."

# Wähle IngressRoute Manifest basierend auf Environment
if [ "${ENVIRONMENT}" = "local" ]; then
    INGRESS_FILE="traefik-ingressroute-local.yaml"
else
    INGRESS_FILE="traefik-ingressroute.yaml"
fi

for resource in "traefik-middlewares.yaml" "${INGRESS_FILE}"; do
    path="${INFRA_DIR}/${resource}"
    if [ -f "$path" ]; then
        kubectl apply -f "$path" -n meeting-automation-staging 2>/dev/null && log_success "  ✓ ${resource} applied" || log_warn "  ⚠ ${resource} failed"
    else
        log_warn "  ⚠ ${resource} not found"
    fi
done

# 8. Health Check
if [ "${ENVIRONMENT}" = "local" ]; then
    # Local: Prüfe Backend Service direkt via ClusterIP (NodePort in Kind nicht host-erreichbar)
    BACKEND_CLUSTER_IP=$(kubectl get svc backend -n meeting-automation-staging -o jsonpath="{.clusterIP}")
    STAGING_URL="http://${BACKEND_CLUSTER_IP}:8000"
    log_info "Local Environment: Prüfe Backend ClusterIP direkt: ${STAGING_URL}/health"
else
    STAGING_URL="https://staging.meeting-automate.tn"
    log_info "Prüfe Health Check: ${STAGING_URL}/health"
fi

HEALTH_OK=false
for i in {1..60}; do
    if [ "${ENVIRONMENT}" = "local" ]; then
        # Für local: curl vom Pod-Netzwerk aus (kubectl run)
        if kubectl run -i --rm --image=curlimages/curl:latest curl-test \
            --namespace=meeting-automation-staging \
            --command -- curl -s -f "${STAGING_URL}/health" &>/dev/null; then
            HEALTH_OK=true
            log_success "Local Health Check OK (via ClusterIP)."
            break
        fi
    else
        # Für staging/production: Direkter HTTP(s) Aufruf
        STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${STAGING_URL}/health" 2>/dev/null || echo "000")
        if [ "${STATUS}" = "200" ]; then
            HEALTH_OK=true
            log_success "Staging Health Check OK (HTTP 200)."
            break
        fi
    fi
    log_info "Health Check failed, Versuch ${i}/60..."
    sleep 5
done

if [ "${HEALTH_OK}" = false ]; then
    log_error "Health Check failed nach 60 Versuchen."
    log_error "Bitte prüfe:"
    log_info "  kubectl get pods -n meeting-automation-staging"
    log_info "  kubectl logs -n meeting-automation-staging deployment/backend"
    exit 1
fi

# 9. E2E Test User Secret
log_info "Erstelle/Update E2E Test-User Secret..."

# Default Werte (können durch .env überschrieben werden)
E2E_EMAIL="${STAGING_E2E_USER_EMAIL:-e2e-tester@staging.meeting.tn}"
E2E_PASSWORD="${STAGING_E2E_USER_PASSWORD:-Password123!}"

kubectl create secret generic e2e-test-user \
    --namespace meeting-automation-staging \
    --from-literal=E2E_TEST_USER_EMAIL="${E2E_EMAIL}" \
    --from-literal=E2E_TEST_USER_PASSWORD="${E2E_PASSWORD}" \
    --dry-run=client -o yaml | kubectl apply -f -
log_success "E2E Test-User Secret gesetzt (Email: ${E2E_EMAIL})."

# 10. AI API Keys Secret
log_info "Erstelle/Update backend-api-keys-staging Secret..."

# Lade .env falls vorhanden
if [ -f "${PROJECT_ROOT}/.env" ]; then
    # shellcheck source=/dev/null
    source "${PROJECT_ROOT}/.env" 2>/dev/null || true
fi

MISTRAL_KEY="${MISTRAL_API_KEY:-}"
GLADIA_KEY="${GLADIA_API_KEY:-}"

if [ -z "${MISTRAL_KEY}" ] || [ -z "${GLADIA_KEY}" ]; then
    log_warn "MISTRAL_API_KEY oder GLADIA_API_KEY nicht in .env gefunden."
    log_warn "Bitte setze Umgebungsvariablen oder erstelle Secret manuell."
else
    kubectl create secret generic backend-api-keys-staging \
        --namespace meeting-automation-staging \
        --from-literal=MISTRAL_API_KEY="${MISTRAL_KEY}" \
        --from-literal=GLADIA_API_KEY="${GLADIA_KEY}" \
        --dry-run=client -o yaml | kubectl apply -f -
    log_success "AI API Keys Secret gesetzt."
fi

# 11. E2E Test User in Datenbank anlegen (wenn nicht übersprungen)
if [ "${SKIP_SEEDS}" = false ]; then
    log_info "Lege E2E Test-User in Datenbank an..."

    # Finde backend Pod
    BACKEND_POD=$(kubectl get pods -n meeting-automation-staging -l app=backend -o jsonpath="{.items[0].metadata.name}" 2>/dev/null || echo "")

    if [ -z "${BACKEND_POD}" ]; then
        log_warn "Backend Pod nicht gefunden, überspringe Seeding."
    else
        # Führe seed_users.py im Pod aus
        log_info "Führe seed_users.py im Backend Pod aus..."
        if kubectl exec -n meeting-automation-staging "${BACKEND_POD}" -- python backend/scripts/seed_users.py 2>&1 | grep -q "completed"; then
            log_success "Test-User erfolgreich gesetzt (oder bereits vorhanden)."
        else
            log_warn "Seeding via Python script fehlgeschlagen, versuche API-Registrierung..."

            # Alternative: Direkte API-Registrierung
            REGISTER_PAYLOAD=$(jq -n \
                --arg email "${E2E_EMAIL}" \
                --arg password "${E2E_PASSWORD}" \
                --arg name "E2E Tester" \
                '{"email": $email, "password": $password, "full_name": $name, "company_name": "E2E Tests"}')

            if curl -s -f -X POST "${STAGING_URL}/api/v1/auth/register" \
                -H "Content-Type: application/json" \
                -d "${REGISTER_PAYLOAD}" 2>/dev/null; then
                log_success "Test-User über API registriert."
            else
                log_warn "API-Registrierung fehlgeschlagen (User existiert vielleicht bereits)."
            fi
        fi
    fi
else
    log_warn "Seeding übersprungen."
fi

# 12. Kubeconfig exportieren (optional)
if [ "${EXPORT_KUBECONFIG}" = true ]; then
    log_info "Exportiere Kubeconfig für Context '${CONTEXT_NAME}'..."
    KUBECONFIG_FILE="${PROJECT_ROOT}/kubeconfig-staging.txt"

    if kubectl config view --context="${CONTEXT_NAME}" --raw > "${KUBECONFIG_FILE}" 2>/dev/null; then
        log_success "Kubeconfig geschrieben nach: ${KUBECONFIG_FILE}"
        echo ""
        log_info "=================================================="
        log_info "Inhalt für GitHub Secret 'KUBE_CONFIG_STAGING':"
        echo ""
        cat "${KUBECONFIG_FILE}"
        echo ""
        log_info "=================================================="
        log_info "Nächste Schritte:"
        log_info "1. Kopiere den obigen Inhalt"
        log_info "2. GitHub: Settings → Secrets and variables → Actions → New repository secret"
        log_info "   Name: KUBE_CONFIG_STAGING"
        log_info "3. Zusätzliche Secrets setzen:"
        log_info "   STAGING_E2E_USER_EMAIL=${E2E_EMAIL}"
        log_info "   STAGING_E2E_USER_PASSWORD=${E2E_PASSWORD}"
        log_info "   MISTRAL_API_KEY_STAGING (aus .env)"
        log_info "   GLADIA_API_KEY_STAGING (aus .env)"
        log_info "   DOCKERHUB_TOKEN (Docker Hub Access Token)"
        echo ""
        log_warn "WICHTIG: Stelle sicher, dass die kubeconfig keine privaten Keys enthält, die nicht für CI bestimmt sind."
    else
        log_error "Konnte Kubeconfig nicht exportieren."
    fi
fi

# Abschluss
echo ""
cat << "EOF"
==================================================
✅ Staging Cluster Setup abgeschlossen!
==================================================

Status Check:
  kubectl get pods -n meeting-automation-staging
  kubectl get ingressroute -n meeting-automation-staging

Health Check:
  curl -k https://staging.meeting-automate.tn/health

Logs ansehen:
  kubectl logs -f deployment/backend -n meeting-automation-staging

Pipeline triggern:
  git add .
  git commit -m "ci: trigger staging after local setup"
  git push origin main

EOF

log_info "Nicht vergessen: GitHub Secrets setzen (falls nicht bereits geschehen)"
log_info "  - KUBE_CONFIG_STAGING (siehe export oben)"
log_info "  - STAGING_E2E_USER_EMAIL=${E2E_EMAIL}"
log_info "  - STAGING_E2E_USER_PASSWORD=${E2E_PASSWORD}"
log_info "  - MISTRAL_API_KEY_STAGING (aus .env)"
log_info "  - GLADIA_API_KEY_STAGING (aus .env)"
log_info "  - DOCKERHUB_TOKEN (Docker Hub Access Token)"
echo ""
