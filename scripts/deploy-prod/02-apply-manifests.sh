#!/bin/bash
# 02-apply-manifests.sh — Apply Kubernetes manifests
# Env: MANIFESTS_DIR (default: /root/production-manifests)
set -e

MANIFESTS_DIR="${MANIFESTS_DIR:-/root/production-manifests}"
cd "$MANIFESTS_DIR"

echo "=== Applying manifests ==="
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

kubectl apply -f namespace.yaml

# Secrets: Only apply if they don't exist (manual update required for changes)
for secret in backend-secrets postgres-secrets redis-secrets minio-secrets rabbitmq-secrets livekit-secrets n8n-secrets; do
  kubectl get secret "$secret" -n meeting-automation >/dev/null 2>&1 || \
    kubectl apply -f "${secret}.yaml" -n meeting-automation
done

kubectl apply -f backend-config.yaml -f livekit-configmap.yaml -f livekit-egress-configmap.yaml -f frontend-nginx-config.yaml
kubectl apply -f redis-deployment.yaml -f rabbitmq-statefulset.yaml -f minio-statefulset.yaml
kubectl apply -f cnpg-cluster.yaml
kubectl apply -f cnpg-scheduled-backup.yaml 2>/dev/null || echo "⚠️ ScheduledBackup already exists or CRD missing"
kubectl apply -f backend-deployment.yaml -f frontend-deployment.yaml -f onlyoffice-deployment.yaml -f n8n-deployment.yaml
kubectl apply -f celery-worker-deployment.yaml -f celery-worker-pro-deployment.yaml -f celery-beat-deployment.yaml
kubectl apply -f network-policies.yaml
kubectl apply -f ingress-prod.yaml
kubectl apply -f n8n-ingress.yaml

echo "✅ Manifests applied"
