#!/bin/bash
# =============================================================================
# Longhorn Setup Script for OCI Staging
# =============================================================================
# This script installs Longhorn v1.12.0 on OCI Staging k3s cluster.
# Used after cluster rebuilds to restore Longhorn storage.
#
# HARTE LESSONS (from Phase 188):
# - LH1: createDefaultDiskLabeledNodes=true is REQUIRED for Single-Node ARM64
# - LH8: "Löschen ist verboten" — analyze before deleting
#
# Usage:
#   chmod +x longhorn-setup.sh
#   ./longhorn-setup.sh
# =============================================================================

set -euo pipefail

# Configuration
LONGHORN_VERSION="1.12.0"
LONGHORN_NAMESPACE="longhorn-system"

# Dynamic node IP detection (no hardcoded IPs!)
NODE_IP="${NODE_IP:-$(kubectl get nodes -o jsonpath='{.items[0].status.addresses[?(@.type=="InternalIP")].address}')}
if [ -z "${NODE_IP}" ]; then
    echo "❌ ERROR: Could not detect node IP"
    exit 1
fi

echo "============================================="
echo "Longhorn Setup for OCI Staging"
echo "============================================="
echo "Node IP: ${NODE_IP}"
echo "Namespace: ${LONGHORN_NAMESPACE}"
echo "============================================="
echo ""

# Step 1: Check if Longhorn is already installed
echo "[1/6] Checking if Longhorn is already installed..."
if kubectl get namespace "${LONGHORN_NAMESPACE}" &>/dev/null; then
    echo "  ✅ Namespace ${LONGHORN_NAMESPACE} exists"
    if kubectl get pods -n "${LONGHORN_NAMESPACE}" -l app=longhorn-manager --no-headers 2>/dev/null | grep -q Running; then
        echo "  ✅ Longhorn is already running"
        echo ""
        echo "Skipping installation. Longhorn is already healthy."
        exit 0
    fi
    echo "  ⚠️  Namespace exists but Longhorn is not running"
else
    echo "  ❌ Namespace ${LONGHORN_NAMESPACE} does not exist"
fi
echo ""

# Step 2: Add Longhorn Helm repo
echo "[2/6] Adding Longhorn Helm repository..."
helm repo add longhorn https://charts.longhorn.io 2>/dev/null || true
helm repo update
echo "  ✅ Helm repo updated"
echo ""

# Step 3: Install Longhorn via Helm
echo "[3/6] Installing Longhorn v${LONGHORN_VERSION}..."
echo "  ⚠️  Using defaultClass=false because local-path already exists"
echo "  ⚠️  For fresh installs without local-path, use defaultClass=true"
helm install longhorn longhorn/longhorn \
    --namespace "${LONGHORN_NAMESPACE}" \
    --create-namespace \
    --version "${LONGHORN_VERSION}" \
    --set defaultSettings.defaultReplicaCount=1 \
    --set defaultSettings.guaranteedInstanceManagerCPU=200 \
    --set defaultSettings.createDefaultDiskLabeledNodes=true \
    --set defaultSettings.defaultClass=false \
    --wait \
    --timeout 10m
echo "  ✅ Longhorn installed"
echo ""

# Step 4: Wait for pods to be ready
echo "[4/6] Waiting for Longhorn pods to be ready..."
echo "  This may take 2-3 minutes..."
kubectl wait --for=condition=ready pod \
    -l app=longhorn-manager \
    -n "${LONGHORN_NAMESPACE}" \
    --timeout=300s
echo "  ✅ All Longhorn manager pods are ready"
echo ""

# Step 5: Verify installation
echo "[5/6] Verifying Longhorn installation..."
echo ""
echo "  Pods:"
kubectl get pods -n "${LONGHORN_NAMESPACE}" -l app=longhorn-manager -o wide
echo ""
echo "  StorageClasses:"
kubectl get storageclass | grep longhorn
echo ""
echo "  DaemonSet:"
kubectl get daemonset -n "${LONGHORN_NAMESPACE}" longhorn-csi-plugin
echo ""

# Step 6: Apply metrics-server EndpointSlice (dynamic node IP)
echo "[6/8] Applying metrics-server EndpointSlice with dynamic node IP (${NODE_IP})..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENDPOINTSLICE_SCRIPT="${SCRIPT_DIR}/apply-metrics-endpointslice.sh"
if [ -f "${ENDPOINTSLICE_SCRIPT}" ]; then
    bash "${ENDPOINTSLICE_SCRIPT}"
    echo "  ✅ metrics-server EndpointSlice applied"
else
    echo "  ⚠️  ${ENDPOINTSLICE_SCRIPT} not found — applying manually"
    kubectl apply -f - <<EOF
apiVersion: discovery.k8s.io/v1
kind: EndpointSlice
metadata:
  name: metrics-server-nodeport
  namespace: kube-system
  labels:
    kubernetes.io/service-name: metrics-server
addressType: IPv4
ports:
- name: https
  port: 4443
  protocol: TCP
endpoints:
- addresses:
  - ${NODE_IP}
  conditions:
    ready: true
EOF
    echo "  ✅ metrics-server EndpointSlice applied"
fi
echo ""

# Step 7: Apply metrics-server patch
echo "[7/8] Applying metrics-server patch..."
METRICS_PATCH="$(dirname "$SCRIPT_DIR")/system/metrics-server-patch.yaml"
if [ -f "${METRICS_PATCH}" ]; then
    kubectl apply -f "${METRICS_PATCH}"
    echo "  ✅ metrics-server patch applied"
else
    echo "  ⚠️  ${METRICS_PATCH} not found — skipping"
fi
echo ""

# Step 8: Apply cleanup CronJob
echo "[8/8] Applying longhorn-cleanup CronJob..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLEANUP_YAML="${SCRIPT_DIR}/../system/longhorn-cleanup-cronjob.yaml"
if [ -f "${CLEANUP_YAML}" ]; then
    kubectl apply -f "${CLEANUP_YAML}" -n "${LONGHORN_NAMESPACE}"
    echo "  ✅ longhorn-cleanup CronJob applied"
else
    echo "  ⚠️  ${CLEANUP_YAML} not found — skipping CronJob"
fi
echo ""

# Final verification
echo "============================================="
echo "Longhorn Setup Complete!"
echo "============================================="
echo ""
echo "Namespace:    $(kubectl get namespace ${LONGHORN_NAMESPACE} -o jsonpath='{.status.phase}')"
echo "Manager:      $(kubectl get pods -n ${LONGHORN_NAMESPACE} -l app=longhorn-manager -o jsonpath='{.items[0].status.phase}')"
echo "CSI Plugin:   $(kubectl get daemonset -n ${LONGHORN_NAMESPACE} longhorn-csi-plugin -o jsonpath='{.status.numberReady}')/${kubectl get daemonset -n ${LONGHORN_NAMESPACE} longhorn-csi-plugin -o jsonpath='{.status.desiredNumberScheduled}'} ready"
echo ""
echo "Default StorageClass: $(kubectl get storageclass -o jsonpath='{.items[?(@.metadata.annotations.storageclass\.kubernetes\.io/is-default-class=="true")].metadata.name}')"
echo ""
echo "✅ Longhorn is ready for use!"
