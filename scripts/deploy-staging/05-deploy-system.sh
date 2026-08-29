#!/bin/bash
# 05-deploy-system.sh — Deploy System CronJobs
# Env: KUBECONFIG
set -e

export KUBECONFIG="${KUBECONFIG:-$(pwd)/kubeconfig-staging}"

echo "=== System CronJobs ==="
kubectl apply -f infrastructure/kubernetes/system/ephemeral-storage-cleanup-cronjob.yaml -n kube-system
kubectl apply -f infrastructure/kubernetes/system/pod-garbage-collector-cronjob.yaml -n kube-system
kubectl apply -f infrastructure/kubernetes/system/longhorn-cleanup-cronjob.yaml -n longhorn-system 2>&1 || true

echo "=== Image-Cleanup ==="
echo "Image-Cleanup timer: manual install required (see infrastructure/kubernetes/system/image-cleanup-script.sh)"

echo "✅ System deployed"
