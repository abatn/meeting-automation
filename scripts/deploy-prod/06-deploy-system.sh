#!/bin/bash
# 06-deploy-system.sh — Deploy System CronJobs + Image-Cleanup + k3s config
# Env: MANIFESTS_DIR (default: /root/production-manifests)
set -e

MANIFESTS_DIR="${MANIFESTS_DIR:-/root/production-manifests}"
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

echo "=== Deploying System CronJobs ==="

# longhorn-cleanup CronJob (only if longhorn-system namespace exists)
if kubectl get namespace longhorn-system &>/dev/null; then
  echo "longhorn-system namespace found — applying longhorn-cleanup CronJob"
  kubectl apply -f "$MANIFESTS_DIR/system/longhorn-cleanup-cronjob.yaml" -n longhorn-system || {
    echo "Warning: longhorn-cleanup CronJob failed (namespace may not have Longhorn installed yet)"
  }
else
  echo "longhorn-system namespace not found — skipping longhorn-cleanup CronJob"
  echo "To enable: install Longhorn first, then re-run this deployment"
fi

# Deploy System CronJobs (kube-system)
kubectl apply -f "$MANIFESTS_DIR/system/ephemeral-storage-cleanup-cronjob.yaml" -n kube-system || echo "Warning: ephemeral-storage-cleanup failed"
kubectl apply -f "$MANIFESTS_DIR/system/pod-garbage-collector-cronjob.yaml" -n kube-system || echo "Warning: pod-garbage-collector failed"

# Deploy Image-Cleanup (systemd timer)
echo "=== Deploying Image-Cleanup ==="
cp "$MANIFESTS_DIR/system/image-cleanup-script.sh" /usr/local/bin/image-cleanup.sh
chmod +x /usr/local/bin/image-cleanup.sh
cp "$MANIFESTS_DIR/system/image-cleanup.service" /etc/systemd/system/
cp "$MANIFESTS_DIR/system/image-cleanup.timer" /etc/systemd/system/
systemctl daemon-reload
systemctl enable image-cleanup.timer
systemctl start image-cleanup.timer
echo "✅ Image-Cleanup timer enabled (weekly Sunday 03:00 UTC)"

# Deploy k3s config.yaml (identical to Staging)
echo "=== Deploying k3s config.yaml ==="
cp "$MANIFESTS_DIR/k3s-config.yaml" /etc/rancher/k3s/config.yaml
echo "✅ k3s config.yaml deployed"

# Ensure k3s.service uses --config flag
if ! grep -q "\-\-config" /etc/systemd/system/k3s.service; then
  echo "Adding --config flag to k3s.service..."
  sed -i 's|ExecStart=/usr/local/bin/k3s \\|ExecStart=/usr/local/bin/k3s \\\n    --config /etc/rancher/k3s/config.yaml|' /etc/systemd/system/k3s.service
  systemctl daemon-reload
  echo "⚠️ k3s.service updated — k3s restart required"
  export RESTART_K3S=true
else
  echo "✅ --config flag already in k3s.service"
  export RESTART_K3S=false
fi
