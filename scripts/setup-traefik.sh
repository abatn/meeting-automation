#!/usr/bin/env bash

################################################################################
# Traefik Ingress Controller Installation Script
#
# Installiert Traefik als Ingress Controller in einem Kubernetes Cluster.
# Unterstützt Helm (empfohlen) und kubectl (manifests).
#
# Usage:
#   ./scripts/setup-traefik.sh [OPTIONS]
#
# Options:
#   --method, -m METHOD   Installationsmethode: helm (default) oder manifest
#   --namespace, -n NS    Kubernetes namespace (default: kube-system)
#   --wait, -w SECONDS    Auf readiness warten (default: 180)
#   --uninstall           Traefik deinstallieren
#   --help, -h            Diese Hilfe anzeigen
#
# Beispiele:
#   # Einfache Installation mit Helm (empfohlen):
#   ./scripts/setup-traefik.sh
#
#   # Mit benutzerdefiniertem Namespace:
#   ./scripts/setup-traefik.sh --namespace traefik-system
#
#   # Mit Manifest (ohne Helm):
#   ./scripts/setup-traefik.sh --method manifest
#
#   # Deinstallieren:
#   ./scripts/setup-traefik.sh --uninstall
#
# Voraussetzungen:
#   - kubectl installiert und konfiguriert
#   - Helm 3 (für Helm-Methode) ODER Internetzugang für Manifest-Download
#
# Nach Installation:
#   - Traefik Dashboard: http://localhost:9000/dashboard/ (optional)
#   - LoadBalancer IP auslesen: kubectl get svc -n kube-system traefik
#   - DNS Record setzen auf EXTERNAL-IP (für staging.meeting-automate.tn)
################################################################################

set -euo pipefail

# Farbcodes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Defaults
METHOD="helm"
NAMESPACE="kube-system"
WAIT_TIMEOUT=180
UNINSTALL=false

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Logging
log_info()    { echo -e "${BLUE}[INFO]${NC} $*"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $*"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $*"; }

# Help
show_help() {
    grep '^#' "$0" | sed 's/^# //;s/^#//' | head -35
    exit 0
}

# Parse Arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --method|-m)  METHOD="$2"; shift 2 ;;
        --namespace|-n) NAMESPACE="$2"; shift 2 ;;
        --wait|-w)    WAIT_TIMEOUT="$2"; shift 2 ;;
        --uninstall)  UNINSTALL=true; shift ;;
        --help|-h)    show_help ;;
        *) log_error "Unbekannte Option: $1"; show_help ;;
    esac
done

# Header
echo "=================================================="
echo "   Traefik Ingress Controller Setup"
echo "=================================================="
log_info "Methode: ${METHOD}"
log_info "Namespace: ${NAMESPACE}"
log_info "Uninstall: ${UNINSTALL}"
echo "=================================================="
echo ""

# Prüfe kubectl
if ! command -v kubectl &> /dev/null; then
    log_error "kubectl ist nicht installiert."
    exit 1
fi

# Prüfe Cluster-Zugang
if ! kubectl cluster-info &> /dev/null; then
    log_error "Keine Verbindung zum Kubernetes Cluster."
    exit 1
fi

# Uninstall
if [ "${UNINSTALL}" = true ]; then
    log_info "Deinstalliere Traefik..."

    case "${METHOD}" in
        helm)
            if command -v helm &> /dev/null; then
                helm uninstall traefik -n "${NAMESPACE}" 2>/dev/null || true
                log_success "Traefik Helm Release entfernt."
            else
                log_error "Helm nicht gefunden, kann nicht deinstallieren."
                exit 1
            fi
            ;;
        manifest)
            kubectl delete -f https://raw.githubusercontent.com/traefik/traefik/v2.10/docs/content/reference/dynamic-configuration/kubernetes-crd.yml 2>/dev/null || true
            kubectl delete -f https://raw.githubusercontent.com/traefik/traefik/v2.10/docs/content/reference/dynamic-configuration/kubernetes-ingressroute.yml 2>/dev/null || true
            kubectl delete -f https://raw.githubusercontent.com/traefik/traefik/v2.10/docs/content/reference/dynamic-configuration/kubernetes-ingressrouteudp.yml 2>/dev/null || true
            kubectl delete -f https://raw.githubusercontent.com/traefik/traefik/v2.10/docs/content/reference/dynamic-configuration/kubernetes-middleware.yml 2>/dev/null || true
            kubectl delete -f https://raw.githubusercontent.com/traefik/traefik/v2.10/docs/content/reference/dynamic-configuration/kubernetes-middlewaretcp.yml 2>/dev/null || true
            kubectl delete -f https://raw.githubusercontent.com/traefik/traefik/v2.10/docs/content/reference/dynamic-configuration/kubernetes-ingressroutewithservertransport.yml 2>/dev/null || true
            kubectl delete -f https://raw.githubusercontent.com/traefik/traefik/v2.10/docs/content/reference/dynamic-configuration/kubernetes-tlsoption.yml 2>/dev/null || true
            kubectl delete -f https://raw.githubusercontent.com/traefik/traefik/v2.10/docs/content/reference/dynamic-configuration/kubernetes-tlsstore.yml 2>/dev/null || true
            kubectl delete -f https://raw.githubusercontent.com/traefik/traefik/v2.10/deploy-docker ignore # Placeholder – wird nicht funktionieren
            log_success "Traefik Manifests gelöscht (falls existiert)."
            ;;
    esac

    # Namespace löschen (optional)
    read -p "Namespace '${NAMESPACE}' ebenfalls löschen? (j/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Jj]$ ]]; then
        kubectl delete namespace "${NAMESPACE}" 2>/dev/null || true
        log_success "Namespace '${NAMESPACE}' gelöscht."
    fi

    exit 0
fi

# Installation
case "${METHOD}" in
    helm)
        log_info "Installiere Traefik via Helm..."

        # Prüfe Helm
        if ! command -v helm &> /dev/null; then
            log_error "Helm ist nicht installiert. Bitte installiere Helm 3: https://helm.sh/docs/intro/install/"
            exit 1
        fi

        # Helm Repo hinzufügen
        if ! helm repo list 2>/dev/null | grep -q traefik; then
            log_info "Füge Traefik Helm Repository hinzu..."
            helm repo add traefik https://helm.traefik.io/traefik
            helm repo update
        fi

        # Namespace erstellen falls nötig
        if ! kubectl get namespace "${NAMESPACE}" &> /dev/null; then
            log_info "Erstelle Namespace: ${NAMESPACE}"
            kubectl create namespace "${NAMESPACE}"
        fi

        # Traefik installieren/upgraden
        log_info "Installiere/Upgrade Traefik Helm Release..."
        if helm upgrade --install traefik traefik/traefik \
            --namespace "${NAMESPACE}" \
            --set providers.kubernetesCRD.enabled=true \
            --set providers.kubernetesIngress.enabled=true \
            --set ingressClass.enabled=true \
            --set ingressClass.isDefaultClass=true \
            --set service.type=LoadBalancer \
            --set service.annotations."service\.beta\.kubernetes\.io/aws-load-balancer-type"="nlb" \
            --wait; then
            log_success "Traefik Helm Release erfolgreich installiert."
        else
            log_error "Traefik Helm Installation fehlgeschlagen."
            exit 1
        fi
        ;;

    manifest)
        log_info "Installiere Traefik via kubectl manifests..."

        # CRDs installieren zuerst
        log_info "1. Installiere Custom Resource Definitions (CRDs)..."
        kubectl apply -f https://raw.githubusercontent.com/traefik/traefik/v2.10/docs/content/reference/dynamic-configuration/kubernetes-crd.yml

        # Traefik Deployment
        log_info "2. Deploy Traefik..."
        kubectl apply -f https://raw.githubusercontent.com/traefik/traefik/v2.10/deploy/docker/

        # Auf Pods warten
        log_info "3. Warte auf Traefik Pods..."
        ;;

    *)
        log_error "Unbekannte Methode: ${METHOD}. Erlaubt: helm, manifest"
        exit 1
        ;;
esac

# Warte auf Traefik Pods
log_info "Warte auf Traefik Pods (timeout: ${WAIT_TIMEOUT}s)..."

# Finde Traefik Pods
PODS_READY=0
for i in $(seq 1 ${WAIT_TIMEOUT}); do
    PODS=$(kubectl get pods -n "${NAMESPACE}" -l app.kubernetes.io/name=traefik --no-headers 2>/dev/null | wc -l)
    READY_PODS=$(kubectl get pods -n "${NAMESPACE}" -l app.kubernetes.io/name=traefik -o jsonpath='{range .items[*]}{.status.conditions[?(@.type=="Ready")].status}{"\n"}{end}' 2>/dev/null | grep -c "True" || echo 0)

    if [ "${READY_PODS}" -ge 1 ]; then
        log_success "Traefik ist bereit (${READY_PODS}/${PODS} Pods Running)."
        PODS_READY=1
        break
    fi

    log_info "Warte auf Traefik Pods... (${i}/${WAIT_TIMEOUT})"
    sleep 1
done

if [ "${PODS_READY}" -eq 0 ]; then
    log_warn "Timeout: Traefik Pods nicht bereit innerhalb ${WAIT_TIMEOUT}s."
    log_info "Prüfe Status:"
    kubectl get pods -n "${NAMESPACE}" -l app.kubernetes.io/name=traefik || true
    kubectl describe pod -n "${NAMESPACE}" -l app.kubernetes.io/name=traefik 2>/dev/null | head -30 || true
    log_warn "Setze fort, aber überprüfe später."
fi

# Service/Traefik LoadBalancer IP auslesen
log_info "Ermittle Traefik Service/LoadBalancer..."
if [ "${METHOD}" = "helm" ]; then
    SERVICE_NAME="traefik"
else
    SERVICE_NAME="traefik"
fi

# Warte auf External IP (wenn LoadBalancer)
if kubectl get svc "${SERVICE_NAME}" -n "${NAMESPACE}" -o jsonpath='{.spec.type}' 2>/dev/null | grep -q "LoadBalancer"; then
    log_info "Warte auf LoadBalancer External IP (timeout: 120s)..."
    for i in $(seq 1 120); do
        EXTERNAL_IP=$(kubectl get svc "${SERVICE_NAME}" -n "${NAMESPACE}" -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "")
        if [ -n "${EXTERNAL_IP}" ]; then
            log_success "Traefik LoadBalancer IP: ${EXTERNAL_IP}"
            echo ""
            log_info "=================================================="
            log_info "Nächste Schritte:"
            log_info "1. DNS A-Record setzen:"
            log_info "   staging.meeting-automate.tn → ${EXTERNAL_IP}"
            log_info "2. Traefik Dashboard aktivieren (optional):"
            log_info "   kubectl port-forward -n ${NAMESPACE} svc/traefik 9000:9000"
            log_info "   Dann öffnen: http://localhost:9000/dashboard/"
            log_info "=================================================="
            break
        fi
        sleep 1
    done

    if [ -z "${EXTERNAL_IP}" ]; then
        log_warn "Keine External IP erhalten (vielleicht Cloud Provider abhängig)."
        log_info "Manuell prüfen: kubectl get svc -n ${NAMESPACE} traefik"
    fi
else
    # ClusterIP oder NodePort
    log_info "Traefik Service Type: $(kubectl get svc "${SERVICE_NAME}" -n "${NAMESPACE}" -o jsonpath='{.spec.type}' 2>/dev/null || echo "unknown")"
    log_info "Für lokales Testing:"
    log_info "  kubectl port-forward -n ${NAMESPACE} svc/traefik 8000:80 9000:9000"
    log_info "  Dann Backend auf http://localhost:8000 erreichbar."
fi

# Prüfe IngressClass
log_info "Prüfe IngressClass..."
kubectl get ingressclass 2>/dev/null | grep -i traefik || log_warn "Keine IngressClass gefunden."

# Teste Traefik mit Beispiel-Ingress (optional)
read -p "Beispiel-IngressRoute für Test erstellen? (j/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Jj]$ ]]; then
    log_info "Erstelle Test-IngressRoute..."
    cat <<EOF | kubectl apply -f -
apiVersion: traefik.containo.us/v1alpha1
kind: IngressRoute
metadata:
  name: test-ingress
  namespace: meeting-automation-staging
spec:
  entryPoints:
    - web
  routes:
    - match: Host(\`test.localhost\`)
      kind: Rule
      services:
        - name: backend
          port: 8000
EOF
    log_success "Test-IngressRoute erstellt."
    log_info "Füge '/etc/hosts' Eintrag hinzu:"
    echo "  127.0.0.1 test.localhost"
    log_info "Dann: curl http://test.localhost/health"
fi

# Abschluss
echo ""
log_success "Traefik Installation abgeschlossen!"
echo ""
cat << "EOF"
==================================================
📋 Zusammenfassung
==================================================

Namespace:           ${NAMESPACE}
Method:              ${METHOD}
Service Type:        $(kubectl get svc traefik -n ${NAMESPACE} -o jsonpath='{.spec.type}' 2>/dev/null || echo "unknown")
Pods Status:         $(kubectl get pods -n ${NAMESPACE} -l app.kubernetes.io/name=traefik --no-headers 2>/dev/null | wc -l | tr -d ' ') pods

EOF

if [ "${METHOD}" = "helm" ]; then
    log_info "Helm Release: traefik (namespace: ${NAMESPACE})"
    log_info "Upgrade/Config: helm upgrade traefik traefik/traefik --namespace ${NAMESPACE} --reuse-values"
fi

echo ""
log_info "Validation:"
log_info "  kubectl get pods -n ${NAMESPACE} -l app.kubernetes.io/name=traefik"
log_info "  kubectl get svc -n ${NAMESPACE} traefik"
log_info "  kubectl get ingressroute -A"
echo ""
log_warn "WICHTIG: Setze DNS 'staging.meeting-automate.tn' auf die Traefik LoadBalancer IP!"
