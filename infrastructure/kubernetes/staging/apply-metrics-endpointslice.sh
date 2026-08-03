#!/bin/bash
# =============================================================================
# Dynamic Metrics-Server EndpointSlice Creator
# =============================================================================
# Phase 189: OCI VNIC blocks pod→node traffic on port 10250
# Fix: hostNetwork=true + secure-port=4443 + EndpointSlice with DYNAMIC node IP
#
# This script detects the node IP dynamically and creates the EndpointSlice.
# No hardcoded IPs — survives node IP changes.
#
# Usage:
#   chmod +x apply-metrics-endpointslice.sh
#   ./apply-metrics-endpointslice.sh
# =============================================================================

set -euo pipefail

echo "============================================="
echo "Metrics-Server EndpointSlice Creator"
echo "============================================="

# Step 1: Detect node IP dynamically
echo "[1/2] Detecting node IP..."
NODE_IP=$(kubectl get nodes -o jsonpath='{.items[0].status.addresses[?(@.type=="InternalIP")].address}')

if [ -z "${NODE_IP}" ]; then
    echo "  ❌ ERROR: Could not detect node IP"
    exit 1
fi
echo "  ✅ Node IP: ${NODE_IP}"
echo ""

# Step 2: Create EndpointSlice with dynamic IP
echo "[2/2] Creating EndpointSlice with node IP ${NODE_IP}..."
cat <<EOF | kubectl apply -f -
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

echo "  ✅ EndpointSlice created with node IP: ${NODE_IP}"
echo ""

# Verify
echo "============================================="
echo "Verification"
echo "============================================="
echo ""
echo "EndpointSlice:"
kubectl get endpointslice metrics-server-nodeport -n kube-system -o jsonpath='{.endpoints[0].addresses[0]}'
echo ""
echo ""
echo "APIService:"
kubectl get apiservice v1beta1.metrics.k8s.io -o jsonpath='{.status.conditions[0].type}: {.status.conditions[0].status}'
echo ""
echo ""
echo "kubectl top nodes:"
kubectl top nodes
echo ""
echo "✅ Metrics-Server EndpointSlice applied successfully!"
