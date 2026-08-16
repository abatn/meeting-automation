#!/bin/bash
# 05-deploy-system.sh — Deploy System CronJobs + Monitoring Stack + Metrics-Server
# Env: KUBECONFIG
set -e

export KUBECONFIG="${KUBECONFIG:-$(pwd)/kubeconfig-staging}"

echo "=== System CronJobs ==="
kubectl apply -f infrastructure/kubernetes/system/ephemeral-storage-cleanup-cronjob.yaml -n kube-system
kubectl apply -f infrastructure/kubernetes/system/pod-garbage-collector-cronjob.yaml -n kube-system
kubectl apply -f infrastructure/kubernetes/system/longhorn-cleanup-cronjob.yaml -n longhorn-system 2>&1 || true

echo "=== Metrics-Server ==="
kubectl apply -f infrastructure/kubernetes/system/metrics-server-patch.yaml -n kube-system

echo "=== Monitoring Stack ==="
kubectl create namespace monitoring --dry-run=client -o yaml | kubectl apply -f -
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts 2>/dev/null || true
helm repo update
helm upgrade kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  -n monitoring --reuse-values \
  --set prometheus.prometheusSpec.hostNetwork=true \
  --set prometheus.prometheusSpec.dnsPolicy=ClusterFirstWithHostNet \
  --set prometheus.service.port=9090 || true
kubectl apply -f infrastructure/kubernetes/staging/monitoring/ -n monitoring 2>&1 || true

echo "=== Image-Cleanup ==="
echo "Image-Cleanup timer: manual install required (see infrastructure/kubernetes/system/image-cleanup-script.sh)"

echo "✅ System + Monitoring deployed"
